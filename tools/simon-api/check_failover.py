#!/usr/bin/env python3
"""Check: node rotation and failover in the gateway, without a network (run_job is replaced)."""
import json, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
json.dump({"m": [{"bootstrap": "a", "model_hash": "m"}, {"bootstrap": "b", "model_hash": "m"}]}, f)
f.close()
os.environ["SIMON_API_NODES"] = f.name
import simon_api as g


def outcome(fn):
    """The exception type a call raises, or its return value."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - the check inspects the type
        return e


def fake(node, req, mt):
    if node["bootstrap"] == "a":
        raise RuntimeError("unreachable")
    return {"ok": node["bootstrap"]}


g.run_job = fake
assert [n["bootstrap"] for n in g.nodes_in_turn("m")] == ["a", "b"]
assert [n["bootstrap"] for n in g.nodes_in_turn("m")] == ["b", "a"]                     # rotation
assert g.run_on_nodes(g.nodes_in_turn("m"), {}, 8) == {"ok": "b"}                       # a fails -> b

g.run_job = lambda n, r, m: (_ for _ in ()).throw(RuntimeError("node_zajety"))
e = outcome(lambda: g.run_on_nodes(g.nodes_in_turn("m"), {}, 8))
assert isinstance(e, RuntimeError) and str(e).startswith("node_zajety")                 # all busy -> 503

g.run_job = lambda n, r, m: (_ for _ in ()).throw(subprocess.TimeoutExpired("x", 1))
assert isinstance(outcome(lambda: g.run_on_nodes(g.nodes_in_turn("m"), {}, 8)),
                  subprocess.TimeoutExpired)                                            # never retried
os.unlink(f.name)
print("failover ok")
