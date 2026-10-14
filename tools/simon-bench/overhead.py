#!/usr/bin/env python3
"""SIMON overhead on one backend: the same jobs sent directly to the engine vs through a SIMON node.

Closed loop: C workers, each sends its next request as soon as the previous one returns, C*runs requests.
Both arms are non-streaming chat completions with the same prompt (unique prefix per request, so no prefix
cache hits) and the same max_tokens, so the difference is the SIMON path: agent process start, libp2p
dial, node admission/queue, receipt signing and client-side receipt verification.

  overhead.py --mode direct --url http://127.0.0.1:8000 --model qwen3.8-27b-bf16 --c 4 --out r.jsonl
  overhead.py --mode simon --bootstrap /ip4/127.0.0.1/tcp/9001/p2p/<id> --model qwen3.8-27b-bf16 --c 4 --out r.jsonl
"""
import argparse, json, statistics, subprocess, threading, time, urllib.request

PROMPT = ("Write a detailed technical explanation of how a distributed network can verify that a remote "
          "GPU actually performed an AI inference job. Cover signatures, re-execution audits, numerical "
          "drift between GPU vendors, and economic incentives.")


def direct(a, k):
    body = json.dumps({"model": a.model, "messages": [{"role": "user", "content": f"Request #{k}. {PROMPT}"}],
                       "max_tokens": a.n, "temperature": 0.0}).encode()
    req = urllib.request.Request(a.url.rstrip("/") + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            d = json.load(r)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "s": round(time.time() - t0, 3)}
    return {"ok": True, "s": round(time.time() - t0, 3), "tokens": d.get("usage", {}).get("completion_tokens", 0)}


def simon(a, k):
    cmd = [a.bin, "--role", "agent", "--bootstrap", a.bootstrap, "--model-hash", a.model,
           "--prompt", f"Request #{k}. {PROMPT}", "--max-tokens", str(a.n), "--identity-file", a.identity, "--json"]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "s": round(time.time() - t0, 3)}
    s = round(time.time() - t0, 3)
    js = next((l for l in reversed(p.stdout.splitlines()) if l.startswith("{")), None)
    if js is None:
        return {"ok": False, "error": (p.stderr or p.stdout)[-200:], "s": s}
    d = json.loads(js)
    return {"ok": bool(d.get("ok")), "verified": bool(d.get("receipt_zweryfikowany")), "s": s,
            "tokens": d.get("tokens_out", 0), "node_ms": d.get("gen_ms"), "error": d.get("kod")}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["direct", "simon"], required=True)
    ap.add_argument("--url"); ap.add_argument("--bootstrap"); ap.add_argument("--model", required=True)
    ap.add_argument("--bin", default="simon"); ap.add_argument("--identity", default="/tmp/overhead-client.id")
    ap.add_argument("--c", type=int, required=True); ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--n", type=int, default=256); ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--label", default=""); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fn = direct if a.mode == "direct" else simon
    total = a.c * a.runs
    nxt, lock, res = [0], threading.Lock(), []

    def worker():
        while True:
            with lock:
                if nxt[0] >= total:
                    return
                k = nxt[0]; nxt[0] += 1
            r = fn(a, k)
            with lock:
                res.append(r)

    t0 = time.time()
    ts = [threading.Thread(target=worker) for _ in range(a.c)]
    [t.start() for t in ts]; [t.join() for t in ts]
    wall = time.time() - t0
    ok = [r for r in res if r["ok"]]
    lat = [r["s"] for r in ok]
    toks = sum(r.get("tokens", 0) for r in ok)
    summ = {"label": a.label, "mode": a.mode, "c": a.c, "requests": total, "ok": len(ok),
            "verified": sum(1 for r in ok if r.get("verified")) if a.mode == "simon" else None,
            "n": a.n, "tokens": toks, "wall_s": round(wall, 2), "total_tok_s": round(toks / wall, 1),
            "lat_p50_s": pct(lat, 50), "lat_p95_s": pct(lat, 95),
            "mean_tokens": round(toks / len(ok), 1) if ok else None,
            "errors": sorted({str(r.get("error")) for r in res if not r["ok"]})[:5]}
    with open(a.out, "a") as f:
        f.write(json.dumps({"summary": summ, "requests": res}) + "\n")
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
