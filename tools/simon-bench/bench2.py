#!/usr/bin/env python3
"""Client-side benchmark v2: matched concurrency across one or more endpoints, latency percentiles, SLO checks.

Speaks OpenAI /v1/completions (streaming) so llama-server and vLLM go through the same client path.
Each request gets a unique prefix ("Request #k.") so no engine can serve it from a prefix cache;
ignore_eos + fixed max_tokens make every output exactly N tokens long.

  bench2.py --target http://127.0.0.1:18401=4 --label A --out r.jsonl
  bench2.py --target http://127.0.0.1:18401=2 --target http://127.0.0.1:18402=2 --label C --out r.jsonl
SLO (chosen in advance, our pilot criteria, not a universal standard): TTFT <= 3000 ms and >= 10 tok/s per stream.
"""
import argparse, json, statistics, threading, time, urllib.request

PROMPT = ("Write a detailed technical explanation of how a distributed network can verify that a remote "
          "GPU actually performed an AI inference job. Cover signatures, re-execution audits, numerical "
          "drift between GPU vendors, and economic incentives.")
SLO_TTFT_MS, SLO_TOK_S = 3000, 10.0


def one(url, model, k, n):
    body = json.dumps({"model": model, "prompt": f"Request #{k}. {PROMPT}", "max_tokens": n, "temperature": 0,
                       "stream": True, "ignore_eos": True, "cache_prompt": False}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/v1/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); t_first = None; chunks = 0
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                d = json.loads(line[5:])
                if any(c.get("text") for c in d.get("choices", [])):
                    chunks += 1
                    t_first = t_first or time.time()
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)[:200]}
    t_end = time.time()
    # ignore_eos + max_tokens → exactly n tokens; chunk count is a cross-check (one token per chunk).
    tpot = (t_end - t_first) / (n - 1) if t_first and n > 1 else None
    ttft = (t_first - t0) * 1000 if t_first else None
    res = {"url": url, "ok": True, "tokens": n, "chunks": chunks, "ttft_ms": round(ttft) if ttft else None,
           "tpot_ms": round(tpot * 1000, 2) if tpot else None, "tok_s": round(1 / tpot, 2) if tpot else None,
           "total_s": round(t_end - t0, 2)}
    res["slo_met"] = bool(ttft is not None and ttft <= SLO_TTFT_MS and tpot and 1 / tpot >= SLO_TOK_S)
    return res


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", required=True, help="URL=concurrency (repeatable)")
    ap.add_argument("--model", default="x"); ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3); ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    targets = [(t.rsplit("=", 1)[0], int(t.rsplit("=", 1)[1])) for t in a.target]
    plan = [u for u, c in targets for _ in range(c)]
    for u, _ in targets:  # warm-up, not recorded
        one(u, a.model, -1, 16)
    reqs = []; aggs = []
    for run in range(a.runs):
        res = [None] * len(plan)
        def w(i): res[i] = one(plan[i], a.model, run * 1000 + i, a.n)
        t0 = time.time()
        th = [threading.Thread(target=w, args=(i,)) for i in range(len(plan))]
        [t.start() for t in th]; [t.join() for t in th]
        wall = time.time() - t0
        agg = round(sum(r["tokens"] for r in res if r["ok"]) / wall, 2)
        aggs.append(agg); reqs += res
        row = {"label": a.label, "run": run, "targets": a.target, "concurrency": len(plan), "n": a.n,
               "wall_s": round(wall, 2), "aggregate_tok_s": agg, "requests": res}
        with open(a.out, "a") as f:
            f.write(json.dumps(row) + "\n")
    ok = [r for r in reqs if r["ok"]]
    summ = {"label": a.label, "concurrency": len(plan), "n": a.n, "runs": a.runs, "requests": len(reqs),
            "failures": len(reqs) - len(ok), "slo_met": sum(r["slo_met"] for r in ok),
            "aggregate_tok_s_median": statistics.median(aggs),
            "tok_s_per_stream_median": statistics.median(r["tok_s"] for r in ok) if ok else None,
            "ttft_ms_p50": pct([r["ttft_ms"] for r in ok], 50), "ttft_ms_p95": pct([r["ttft_ms"] for r in ok], 95),
            "tpot_ms_p50": pct([r["tpot_ms"] for r in ok], 50), "tpot_ms_p95": pct([r["tpot_ms"] for r in ok], 95)}
    per_url = {}
    for u, _ in targets:
        rs = [r for r in ok if r["url"] == u]
        per_url[u] = {"tok_s_median": statistics.median(r["tok_s"] for r in rs) if rs else None,
                      "ttft_ms_p50": pct([r["ttft_ms"] for r in rs], 50)}
    summ["per_target"] = per_url
    with open(a.out, "a") as f:
        f.write(json.dumps({"summary": summ}) + "\n")
    print(json.dumps(summ), flush=True)


if __name__ == "__main__":
    assert pct([1, 2, 3, 4], 50) in (2, 3) and pct([5], 95) == 5  # self-check
    main()
