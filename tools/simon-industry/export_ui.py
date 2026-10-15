#!/usr/bin/env python3
"""Turn ticket runs (tickets.py JSONL) into the data file of the web UI's /industry page.

    python3 tools/simon-industry/export_ui.py docs/industry/run-*.jsonl > ui/src/lib/industry-run.json

Keeps what the page shows and what the browser needs to re-check each receipt: the receipt and the
exact signed output string. Node labels come from --labels (node_id prefix=label), never guessed.
"""
import json, statistics, sys

KEEP_FEATURES = ("type", "air_K", "process_K", "rpm", "torque_Nm", "wear_min", "temp_diff_K", "power_W", "strain_minNm")


def main(paths, labels):
    recs = []
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            s = r.get("simon") or {}
            rc = s.get("receipt") or {}
            nid = rc.get("node_id") or ""
            recs.append({
                "record": r["record"], "product": r["product"], "label": r["label"],
                "features": {k: r["features"][k] for k in KEEP_FEATURES}, "findings": r["findings"],
                "ticket": r.get("ticket"), "problems": r.get("problems"), "note": r.get("note"),
                "error": r.get("error"), "model": r.get("model"), "wall_ms": r.get("wall_ms"),
                "node_id": nid, "node_label": next((v for k, v in labels.items() if nid.startswith(k)), None),
                "receipt": rc or None, "signed_output": s.get("signed_output"), "run": p.rsplit("/", 1)[-1],
            })
    t = [r for r in recs if r["ticket"] is not None]
    walls = [r["wall_ms"] for r in t if r["wall_ms"]]
    summary = {"records": len(recs), "tickets": len(t), "clean": sum(1 for r in t if not r["problems"]),
               "no_ticket": sum(1 for r in recs if r["ticket"] is None and not r["error"]),
               "errors": sum(1 for r in recs if r["error"]),
               "median_ms": int(statistics.median(walls)) if walls else None,
               "nodes": sorted({r["node_label"] or r["node_id"][:12] for r in t})}
    json.dump({"summary": summary, "records": recs}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    args = sys.argv[1:]
    labels = {}
    while args and args[0] == "--labels":
        k, v = args[1].split("=", 1)
        labels[k] = v
        args = args[2:]
    main(args, labels)
