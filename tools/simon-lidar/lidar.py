#!/usr/bin/env python3
"""LIDAR-style behavioural fingerprint of the model behind an OpenAI-compatible endpoint (pilot).

A SIMON receipt proves which node signed an output, not which model produced it. This tool asks a
different question with a statistical answer: does the agent behaviour of the endpoint match the
reference fingerprint of the model it declares? Idea from LIDAR (Tsinghua, 2026): 3 coding tasks with A/B
variants, behaviour features over the trajectories, Jeffreys-smoothed reference profiles.

This is a pilot, not the paper's method: our own small harness, ~40 hand-made features instead of ~958,
public fixed tasks (a dishonest node can learn and mimic them; production needs a secret, rotating task
pool). The verdict is open-set: consistent / inconsistent / inconclusive, never a bare nearest match.

    lidar.py run    --base URL/v1 --model NAME --label CLASS --n 5 --out fp.jsonl   # collect fingerprints
    lidar.py eval   --refs fp.jsonl                                                # leave-one-out confusion
    lidar.py verify --base URL/v1 --model NAME --declared CLASS --refs fp.jsonl    # one probe -> verdict
"""
import argparse, collections, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, "tasks")
MAX_STEPS = 15
SAMPLING = {"temperature": 0.7, "top_p": 0.9}  # fixed for every model: behaviour, not decoding, is compared
SYSTEM = ("You are a coding agent working in a small Python repository. Use the tools to inspect and change "
          "files and to run the tests. When you are done, call finish with a short summary of what you did.")
# (fixture dir, instruction, inject a failure into the first run_tests call)
VARIANTS = {
    "verify_a": ("verify", "slugify in slug.py has a bug: extra spaces are not handled. Fix it.", False),
    "verify_b": ("verify", "slugify in slug.py has a bug: extra spaces are not handled. Fix it. "
                           "Run the tests before you finish.", False),
    "recover_a": ("recover", "The functions in stats.py do not match their docstrings. Fix them.", False),
    "recover_b": ("recover", "The functions in stats.py do not match their docstrings. Fix them.", True),
    "resolve_a": ("resolve", "Make round_price in prices.py follow the specification in README.md.", False),
    "resolve_b": ("resolve_b", "Make round_price in prices.py follow the specification in README.md.", False),
}
TOOLS = [{"type": "function", "function": f} for f in [
    {"name": "list_files", "description": "List the files in the repository.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "read_file", "description": "Read a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Replace the whole content of a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
    {"name": "run_tests", "description": "Run the unit tests and return the output.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "finish", "description": "Stop working and report what you did.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]]
CONFLICT = re.compile(r"contradict|conflict|inconsisten|mismatch|disagree|sprzeczn|niezgodn", re.I)


# ---------------------------------------------------------------- harness
def chat(base, model, messages, timeout=900):
    body = {"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto", "max_tokens": 1024,
            **SAMPLING}
    r = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def run_tests(work):
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=work,
                       capture_output=True, text=True, timeout=30)
    return p.returncode == 0, (p.stdout + p.stderr)[-1500:] + f"\nexit code {p.returncode}"


def safe(work, path):
    full = os.path.realpath(os.path.join(work, path or ""))
    return full if full.startswith(os.path.realpath(work) + os.sep) else None


def tool(work, name, args, state):
    """Execute one tool call; return (action category, extra, result text)."""
    if name == "list_files":
        files = sorted(os.path.relpath(os.path.join(d, f), work) for d, _, fs in os.walk(work) for f in fs
                       if "__pycache__" not in d)
        return "list", {}, "\n".join(files)
    if name == "read_file":
        p = safe(work, args.get("path"))
        if not p or not os.path.isfile(p):
            return "bad_call", {}, f"error: no such file {args.get('path')!r}"
        return "read", {"path": os.path.relpath(p, work)}, open(p).read()
    if name == "write_file":
        p = safe(work, args.get("path"))
        if not p or not isinstance(args.get("content"), str):
            return "bad_call", {}, "error: write_file needs a path inside the repository and a content string"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(args["content"])
        rel = os.path.relpath(p, work)
        return ("write_test" if rel.startswith("tests") else "write_code"), {"path": rel}, "ok"
    if name == "run_tests":
        if state["inject"] and not state["injected"]:
            state["injected"] = True
            return "test_injected", {}, "ERROR: test runner could not start (resource temporarily unavailable)\nexit code 1"
        ok, out = run_tests(work)
        return ("test_pass" if ok else "test_fail"), {}, out
    if name == "finish":
        return "finish", {"summary": str(args.get("summary", ""))[:2000]}, "ok"
    return "bad_call", {}, f"error: unknown tool {name!r}"


def trajectory(base, model, variant):
    fixture, instruction, inject = VARIANTS[variant]
    work = tempfile.mkdtemp(prefix="lidar-")
    shutil.copytree(os.path.join(TASKS, fixture), work, dirs_exist_ok=True)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": instruction}]
    state, steps, tokens, receipts, calls_n, err = {"inject": inject, "injected": False}, [], 0, 0, 0, None
    t0 = time.time()
    try:
        while len(steps) < MAX_STEPS and not (steps and steps[-1]["act"] == "finish"):
            d = chat(base, model, msgs)
            calls_n += 1
            tokens += (d.get("usage") or {}).get("completion_tokens") or 0
            receipts += 1 if (d.get("simon") or {}).get("receipt_status") == "signature_valid_output_bound" else 0
            m = d["choices"][0]["message"]
            calls = m.get("tool_calls") or []
            msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")} | {"role": "assistant"})
            if not calls:
                steps.append({"act": "text", "chars": len(m.get("content") or "")})
                msgs.append({"role": "user", "content": "Continue. Use the tools, and call finish when you are done."})
                continue
            for c in calls:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = None
                if not isinstance(args, dict):
                    act, extra, out = "bad_call", {}, "error: arguments are not a JSON object"
                else:
                    act, extra, out = tool(work, c["function"].get("name"), args, state)
                steps.append({"act": act, **extra})
                msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out})
                if act == "finish" or len(steps) >= MAX_STEPS:
                    break
    except Exception as e:  # endpoint error: recorded as a state, never dropped
        err = str(e)[:300]
    final_pass, _ = run_tests(work)
    shutil.rmtree(work, ignore_errors=True)
    return {"variant": variant, "steps": steps, "final_pass": final_pass, "completion_tokens": tokens,
            "receipts_verified": receipts, "llm_calls": calls_n, "error": err, "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- features
def bucket(x, edges):
    for e in edges:
        if x <= e:
            return f"<={e}"
    return f">{edges[-1]}"


BIGRAMS = [("read", "write_code"), ("write_code", "test_pass"), ("write_code", "test_fail"), ("test_fail", "write_code"),
           ("test_fail", "test_fail"), ("test_injected", "test_injected"), ("test_injected", "write_code"),
           ("write_code", "finish"), ("test_pass", "finish"), ("read", "read"), ("text", "text"), ("list", "read")]


def features(fp):
    """Categorical features of one fingerprint (6 trajectories). Missing behaviour is a state, not a hole."""
    f = {}
    num = collections.defaultdict(list)
    for t in fp["trajectories"]:
        v, acts = t["variant"], [s["act"] for s in t["steps"]]
        tests = [a for a in acts if a.startswith("test_")]
        writes = [i for i, a in enumerate(acts) if a.startswith("write")]
        f[v + ":steps"] = bucket(len(acts), [3, 6, 10, 14])
        f[v + ":first"] = acts[0] if acts else "none"
        f[v + ":second"] = acts[1] if len(acts) > 1 else "none"
        f[v + ":ran_tests"] = bool(tests)
        f[v + ":tests_before_write"] = ("none" if not writes else
                                        any(a.startswith("test_") for a in acts[:writes[0]]))
        f[v + ":n_tests"] = bucket(len(tests), [0, 1, 2])
        f[v + ":n_writes"] = bucket(len(writes), [0, 1, 2])
        f[v + ":wrote_test"] = "write_test" in acts
        f[v + ":finished"] = "finish" in acts
        f[v + ":final_pass"] = t["final_pass"]
        f[v + ":error"] = t["error"] is not None
        fails = [i for i, a in enumerate(acts) if a in ("test_fail", "test_injected")]
        f[v + ":after_fail"] = acts[fails[0] + 1] if fails and fails[0] + 1 < len(acts) else ("end" if fails else "no_fail")
        reads = [s.get("path") for s in t["steps"] if s["act"] == "read"]
        f[v + ":reread"] = len(reads) != len(set(reads))
        f[v + ":read_before_write"] = "none" if not writes else "read" in acts[:writes[0]]
        pairs = set(zip(acts, acts[1:]))
        for a, b in BIGRAMS:
            f[f"{v}:bg:{a}>{b}"] = (a, b) in pairs
        run = best = 0
        for i, a in enumerate(acts):
            run = run + 1 if i and a == acts[i - 1] else 1
            best = max(best, run)
        f[v + ":max_run"] = bucket(best, [1, 2])
        f[v + ":text_turns"] = bucket(acts.count("text"), [0, 1])
        f[v + ":bad_calls"] = bucket(acts.count("bad_call"), [0])
        summary = next((s.get("summary", "") for s in t["steps"] if s["act"] == "finish"), "")
        f[v + ":summary_len"] = bucket(len(summary), [0, 80, 300])
        f[v + ":conflict"] = bool(CONFLICT.search(summary))
        num["steps"].append(len(acts))
        num["tests"].append(len(tests))
        num["tokens"].append(t["completion_tokens"])
        num["finished"].append(1 if "finish" in acts else 0)
    for k, xs in num.items():  # distribution-level: mean and spread across the 6 trajectories
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
        edges = {"steps": [3, 6, 10], "tests": [0.5, 1.5, 3], "tokens": [200, 600, 1500], "finished": [0.4, 0.8]}[k]
        f["dist:" + k + ":mean"] = bucket(m, edges)
        f["dist:" + k + ":sd"] = bucket(sd, [0.5, 2, 5] if k != "tokens" else [100, 400])
    return {k: str(v) for k, v in f.items()}


# ---------------------------------------------------------------- scoring
def profiles(fps):
    """Per class, per feature: state counts."""
    prof = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for fp in fps:
        for k, s in fp["features"].items():
            prof[fp["label"]][k][s] += 1
    return prof


def score(feat, prof, label, states):
    """Mean Jeffreys-smoothed log-likelihood of the query under one class profile."""
    cls, tot = prof[label], 0.0
    n = sum(next(iter(cls.values())).values()) if cls else 0
    for k, s in feat.items():
        K = len(states[k]) + 1  # +1: room for a state that no reference showed
        tot += math.log((cls[k][s] + 0.5) / (n + 0.5 * K))
    return tot / len(feat)


def all_states(fps):
    st = collections.defaultdict(set)
    for fp in fps:
        for k, s in fp["features"].items():
            st[k].add(s)
    return st


def loo(fps):
    """Leave-one-fingerprint-out: for each fingerprint, its scores against every class profile."""
    out = []
    for i, fp in enumerate(fps):
        rest = fps[:i] + fps[i + 1:]
        prof, st = profiles(rest), all_states(rest)
        out.append((fp["label"], {c: score(fp["features"], prof, c, st) for c in prof}))
    return out


def verdict(feat, fps, declared):
    """Open-set verdict for the declared class: consistent / inconsistent / inconclusive."""
    honest = [s[declared] for lab, s in loo(fps) if lab == declared and declared in s]
    prof, st = profiles(fps), all_states(fps)
    sc = {c: score(feat, prof, c, st) for c in prof}
    best = max(sc, key=sc.get)
    if declared not in sc or len(honest) < 3:
        return {"verdict": "inconclusive", "reason": "fewer than 3 reference fingerprints of the declared class",
                "scores": sc}
    floor = min(honest)  # lowest score an honest fingerprint of this class got in leave-one-out
    if sc[declared] >= floor and best == declared:
        v = "consistent"
    elif sc[declared] < floor and best != declared:
        v = "inconsistent"
    else:
        v = "inconclusive"
    return {"verdict": v, "declared": declared, "best": best, "margin": round(sc[best] - sc[declared], 4),
            "declared_score": round(sc[declared], 4), "honest_floor": round(floor, 4), "n_refs": len(honest),
            "scores": {k: round(x, 4) for k, x in sc.items()}}


# ---------------------------------------------------------------- cli
def fingerprint(base, model, label, log=print):
    trs = []
    for v in VARIANTS:
        t = trajectory(base, model, v)
        log(f"  {label} {v}: {len(t['steps'])} steps, {[s['act'] for s in t['steps']]}, pass={t['final_pass']}, "
            f"{t['seconds']}s" + (f", ERROR {t['error']}" if t["error"] else ""))
        trs.append(t)
    fp = {"label": label, "model": model, "base": base, "trajectories": trs, "time": time.time()}
    fp["features"] = features(fp)
    return fp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--base", required=True); r.add_argument("--model", required=True)
    r.add_argument("--label", required=True); r.add_argument("--n", type=int, default=1); r.add_argument("--out", required=True)
    r.add_argument("--only", help="one variant (smoke test)")
    e = sub.add_parser("eval"); e.add_argument("--refs", required=True, nargs="+")
    v = sub.add_parser("verify"); v.add_argument("--base", required=True); v.add_argument("--model", required=True)
    v.add_argument("--declared", required=True); v.add_argument("--refs", required=True, nargs="+")
    a = ap.parse_args()

    if a.cmd == "run":
        if a.only:
            print(json.dumps(trajectory(a.base, a.model, a.only), indent=1))
            return
        for i in range(a.n):
            fp = fingerprint(a.base, a.model, a.label)
            with open(a.out, "a") as f:
                f.write(json.dumps(fp) + "\n")
            print(f"fingerprint {i + 1}/{a.n} -> {a.out}")
        return
    fps = [json.loads(l) for p in a.refs for l in open(p) if l.strip()]
    for fp in fps:
        fp["features"] = features(fp)  # recompute: feature code may have changed since collection
    if a.cmd == "eval":
        res = [(lab, sc) for lab, sc in loo(fps) if sc]
        if not res:
            sys.exit("eval needs at least 2 fingerprints")
        labels = sorted({l for l, _ in res})
        conf = {l: collections.Counter() for l in labels}
        for lab, sc in res:
            conf[lab][max(sc, key=sc.get)] += 1
        ok = sum(conf[l][l] for l in labels)
        print(f"leave-one-fingerprint-out top-1: {ok}/{len(res)}  (pilot: small N, not an error rate)")
        print("true \\ predicted: " + "  ".join(labels))
        for l in labels:
            print(f"{l}: " + "  ".join(str(conf[l][p]) for p in labels))
        for l in labels:  # open-set check: honest fingerprints judged against their own class
            vs = collections.Counter(verdict(fp["features"], [x for x in fps if x is not fp], l)["verdict"]
                                     for fp in fps if fp["label"] == l)
            print(f"honest {l}: {dict(vs)}")
        return
    fp = fingerprint(a.base, a.model, "probe")
    rep = verdict(fp["features"], fps, a.declared)
    rep["receipts_verified"] = sum(t["receipts_verified"] for t in fp["trajectories"])
    rep["llm_calls"] = sum(t["llm_calls"] for t in fp["trajectories"])
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
