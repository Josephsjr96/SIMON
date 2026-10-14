#!/usr/bin/env python3
"""Client-side speed benchmark for a llama-server endpoint (A, B', D).

Streams /completion, measures time-to-first-token and decode speed on the client,
and records the server's own timings separately. Usage:
  bench.py --url http://127.0.0.1:18401 --label A --runs 3 [--concurrency N] --out results.jsonl
"""
import argparse, json, statistics, threading, time, urllib.request

PROMPT = ("Write a detailed technical explanation of how a distributed network can verify that a remote "
          "GPU actually performed an AI inference job. Cover signatures, re-execution audits, numerical "
          "drift between GPU vendors, and economic incentives.")


def one(url, n_predict):
    body = json.dumps({"prompt": PROMPT, "n_predict": n_predict, "temperature": 0, "stream": True,
                       "cache_prompt": False, "ignore_eos": True}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); t_first = None; chunks = 0; final = {}
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            d = json.loads(line[5:])
            if d.get("content"):
                chunks += 1
                if t_first is None:
                    t_first = time.time()
            if d.get("stop"):
                final = d
    t_end = time.time()
    n = (final.get("timings") or {}).get("predicted_n") or final.get("tokens_predicted") or chunks
    dec_s = (t_end - t_first) if t_first else None
    return {"ttft_ms": round((t_first - t0) * 1000) if t_first else None,
            "total_s": round(t_end - t0, 2), "tokens": n,
            "client_tok_s": round((n - 1) / dec_s, 2) if dec_s and n > 1 else None,
            "server_tok_s": round((final.get("timings") or {}).get("predicted_per_second") or 0, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3); ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--concurrency", type=int, default=1); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    one(a.url, 16)  # warm-up, not recorded
    rows = []
    for run in range(a.runs):
        res = [None] * a.concurrency
        def w(i): res[i] = one(a.url, a.n)
        t0 = time.time()
        th = [threading.Thread(target=w, args=(i,)) for i in range(a.concurrency)]
        [t.start() for t in th]; [t.join() for t in th]
        wall = time.time() - t0
        agg = round(sum(r["tokens"] for r in res) / wall, 2)
        row = {"label": a.label, "run": run, "concurrency": a.concurrency, "wall_s": round(wall, 2),
               "aggregate_tok_s": agg, "requests": res}
        rows.append(row); print(json.dumps(row), flush=True)
        with open(a.out, "a") as f:
            f.write(json.dumps(row) + "\n")
    med = lambda k: statistics.median([r[k] for row in rows for r in row["requests"] if r[k] is not None])
    print(json.dumps({"label": a.label, "concurrency": a.concurrency,
                      "median_ttft_ms": med("ttft_ms"), "median_client_tok_s": med("client_tok_s"),
                      "median_aggregate_tok_s": statistics.median(r["aggregate_tok_s"] for r in rows)}), flush=True)


if __name__ == "__main__":
    main()
