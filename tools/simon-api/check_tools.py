#!/usr/bin/env python3
"""End-to-end check of tool calls through SIMON: what a coding agent (Cline, opencode) needs.

    python3 tools/simon-api/check_tools.py http://127.0.0.1:18600/v1 <model> <simon-bin> <bootstrap>

1. tool call comes back as an OpenAI tool_calls message, finish_reason "tool_calls", receipt verified
2. the tool result goes back in and the model answers
3. stream=true: role chunk, tool_calls delta, finish chunk with the receipt, [DONE]
4. the receipt binds the tool call: one changed argument byte -> the offline verifier rejects it
"""
import json, os, subprocess, sys, tempfile, urllib.request

BASE, MODEL, BIN, BOOT = sys.argv[1:5]
TOOLS = [{"type": "function", "function": {"name": "get_weather", "description": "Get current weather for a city",
          "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
MSG = [{"role": "user", "content": "What is the weather in Warsaw? Use the tool."}]
ok = True


def check(name, cond, info=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, info)


def post(body):
    r = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=600)


d = json.load(post({"model": MODEL, "messages": MSG, "tools": TOOLS, "max_tokens": 150}))
c = d["choices"][0]
tc = c["message"].get("tool_calls") or []
check("1 tool call", tc and tc[0]["function"]["name"] == "get_weather" and c["finish_reason"] == "tool_calls"
      and d["simon"]["receipt_status"] == "signature_valid_output_bound", tc[:1])

if tc:
    msgs = MSG + [c["message"], {"role": "tool", "tool_call_id": tc[0]["id"], "content": '{"temp_c": 11, "sky": "rain"}'}]
    d2 = json.load(post({"model": MODEL, "messages": msgs, "tools": TOOLS, "max_tokens": 80}))
    a = d2["choices"][0]["message"].get("content") or ""
    check("2 answer after tool result", a.strip() and d2["choices"][0]["finish_reason"] == "stop", repr(a[:100]))

chunks, names, last = [], set(), None
with post({"model": MODEL, "messages": MSG, "tools": TOOLS, "max_tokens": 150, "stream": True}) as r:
    for raw in r:
        line = raw.decode().strip()
        if line.startswith("data:"):
            chunks.append(line[5:].strip())
for x in chunks[:-1]:
    j = json.loads(x)
    for t in (j["choices"][0]["delta"].get("tool_calls") or []):
        names.add(t["function"]["name"])
    last = j
check("3 streaming", chunks and chunks[-1] == "[DONE]" and "get_weather" in names
      and last["choices"][0]["finish_reason"] == "tool_calls" and "receipt" in last.get("simon", {}),
      f"{len(chunks)} events")

# 4. the agent's raw output (what the node signed), then one changed byte inside the tool arguments
req = json.dumps({"messages": MSG, "tools": TOOLS})
p = subprocess.run([BIN, "--role", "agent", "--bootstrap", BOOT, "--model-hash", MODEL, "--request-file", "-",
                    "--max-tokens", "150", "--json"], input=req, capture_output=True, text=True, timeout=600)
j = json.loads(next(l for l in reversed(p.stdout.splitlines()) if l.startswith("{")))
with tempfile.TemporaryDirectory() as t:
    rec, out = os.path.join(t, "r.json"), os.path.join(t, "o.txt")
    json.dump(j["receipt"], open(rec, "w"))
    verdict = lambda: subprocess.run([BIN, "--verify-receipt", rec, "--expect-output", out],
                                     capture_output=True, text=True).returncode
    open(out, "w").write(j["output"])
    good = verdict()
    open(out, "w").write(j["output"].replace("Warsaw", "Warsax", 1))
    bad = verdict()
check("4 receipt binds tool arguments", good == 0 and bad != 0 and "Warsaw" in j["output"], f"valid={good} tampered={bad}")
sys.exit(0 if ok else 1)
