#!/usr/bin/env python3
"""SIMON integrity canary — an operator self-check: did this node's weights get corrupted?

Consumer GPUs (RTX 3090, GTX TITAN X, ...) have no ECC. A single flipped bit in a weight's exponent
(Rowhammer on GPU memory — GPUHammer, USENIX Security 2025 — or a plain memory error) can turn a model
into a garbage generator that still answers and still signs valid receipts. This probe catches that:
8 prompts whose first answer word is unambiguous ("anchors"), greedy, 8 tokens each.

Measured (docs/INTEGRITY-CANARY.md): an honest backend hit 8/8 anchors in 16/16 runs, idle and under load,
even though its later tokens vary between runs (batching). Simulated single-bit flips: exponent bit of a
weight-block scale in ffn_down → 0/8; same in an embedding row (tied output head) → 2/8.

Verdict: ok (8/8), warn (1-2 misses), fail (>= 3 misses). It catches CATASTROPHIC corruption only; a flip
that harms only rare contexts passes. It is self-run, so it protects honest operators — a lying node can
special-case public prompts (the protocol fix is hidden, verifier-issued probes; see ROADMAP). The verdict
is self-reported: it is an operator smoke alarm, not network integrity.

A fail is re-checked once right away; only two fails in a row run --on-fail (a load spike or a transient
backend fault should not quarantine an honest node).

    python3 tools/simon-canary/simon_canary.py --backend http://127.0.0.1:18430 \
        --status ~/.simon/canary-demo.json --on-fail "systemctl --user stop simon-demo-node"

Exit: 0 ok/warn, 2 fail, 3 backend unreachable (no verdict — not counted as corruption).
"""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, sys, time, urllib.request

ANCHORS = [
    ("The capital of France is", "Paris"), ("1, 2, 3, 4, 5, 6,", "7"),
    ("Monday, Tuesday, Wednesday,", "Thursday"), ("The chemical symbol for water is", "H2O"),
    ("A, B, C, D, E,", "F"), ("The largest planet in the solar system is", "Jupiter"),
    ("January, February, March,", "April"), ("The opposite of hot is", "cold"),
]
FAIL_AT = 3  # misses; honest runs measured 0 misses in 16/16
PROMPTS_SHA = hashlib.sha256(json.dumps(ANCHORS).encode()).hexdigest()[:16]  # which probe set produced a verdict


def verdict(misses):
    return "ok" if misses == 0 else ("warn" if misses < FAIL_AT else "fail")


def hit(text, anchor):
    return text.strip().strip('"\'').startswith(anchor)


def ask(backend, model, prompt):
    body = {"prompt": prompt, "max_tokens": 8, "temperature": 0,
            "cache_prompt": False}  # llama.cpp: no KV reuse from before a flip; other servers ignore it
    if model:
        body["model"] = model
    req = urllib.request.Request(backend.rstrip("/") + "/v1/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["text"]


def served_model(backend):
    try:
        with urllib.request.urlopen(backend.rstrip("/") + "/v1/models", timeout=10) as r:
            return json.loads(r.read())["data"][0]["id"]
    except (OSError, ValueError, KeyError, IndexError):
        return None


def run(backend, model):
    with cf.ThreadPoolExecutor(len(ANCHORS)) as ex:
        texts = list(ex.map(lambda pa: ask(backend, model, pa[0]), ANCHORS))
    misses = [{"anchor": a, "got": t[:80]} for (_, a), t in zip(ANCHORS, texts) if not hit(t, a)]
    return {"verdict": verdict(len(misses)), "hits": len(ANCHORS) - len(misses), "of": len(ANCHORS),
            "misses": misses, "ts": time.time(), "backend": backend, "served_model": served_model(backend),
            "prompts_sha": PROMPTS_SHA, "self_reported": True}


def write_status(path, st):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, path)  # readers never see a half-written file


def selfcheck():
    assert [verdict(m) for m in (0, 1, 2, 3, 8)] == ["ok", "warn", "warn", "fail", "fail"]
    assert hit(" Paris. The capital", "Paris") and hit(' "Jupiter"', "Jupiter")
    assert not hit(" in性质 oft", "Paris") and not hit(" and April are", "April")


def main():
    selfcheck()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", required=True, help="OpenAI-compatible base URL of the node's inference server")
    ap.add_argument("--model", default="", help="model name, if the server needs one (vLLM)")
    ap.add_argument("--status", default="", help="write the result here (JSON) for tools/simon-monitor")
    ap.add_argument("--on-fail", default="", help="shell command to run on a fail verdict, e.g. stop the node")
    a = ap.parse_args()
    try:
        st = run(a.backend, a.model)
        if st["verdict"] == "fail":
            st = run(a.backend, a.model)  # confirm before acting: two fails in a row
            st["confirmed"] = st["verdict"] == "fail"
    except OSError as e:  # unreachable backend: no verdict, never reported as corruption
        st = {"verdict": "unreachable", "error": str(e)[:200], "ts": time.time()}
    if a.status:
        write_status(os.path.expanduser(a.status), st)
    print(json.dumps(st, ensure_ascii=False))
    if st["verdict"] == "fail":
        if a.on_fail:
            subprocess.run(a.on_fail, shell=True)
        sys.exit(2)
    sys.exit(3 if st["verdict"] == "unreachable" else 0)


if __name__ == "__main__":
    main()
