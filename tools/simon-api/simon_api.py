#!/usr/bin/env python3
"""SIMON API — an OpenAI-compatible HTTP front for SIMON nodes (local test gateway).

Every chat completion becomes one SIMON job: `simon --role agent ... --json`.
The answer comes back with the node's signed receipt and the client-side verdict.

    SIMON_BIN=target/release/simon SIMON_API_NODES=nodes.json python3 tools/simon-api/simon_api.py
    curl -s 127.0.0.1:18600/v1/chat/completions -d '{"model":"qwen3.8-27b-bf16","messages":[...]}'

nodes.json: {"<model name>": {"bootstrap": "/ip4/.../tcp/.../p2p/<peer_id>", "model_hash": "..."}}

What a receipt proves here: the node's key signed this exact output for this job
(proof level 0). It does NOT prove which model ran — see docs/THREAT-MODEL.md.
"""
import json, os, subprocess, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIN = os.environ.get("SIMON_BIN", "simon")
HOST, PORT = "127.0.0.1", int(os.environ.get("SIMON_API_PORT", "18600"))
TIMEOUT_S = int(os.environ.get("SIMON_API_TIMEOUT", "600"))
IDENTITY = os.environ.get("SIMON_API_IDENTITY", os.path.expanduser("~/.simon/api-client.id"))
# Optional job log for tools/simon-monitor: one JSON line per completed job. Receipt fields and
# timings only — never the prompt or the output.
JOBLOG = os.environ.get("SIMON_API_JOBLOG", "")
_joblog_lock = threading.Lock()
NODES = json.load(open(os.environ["SIMON_API_NODES"])) if os.environ.get("SIMON_API_NODES") else {}


def to_prompt(messages):
    # ponytail: the SIMON agent takes one prompt string, so roles are flattened into text.
    # Upgrade path: a multi-message field in the protocol.
    parts = []
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, list):  # OpenAI content parts: keep text only
            c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
        parts.append(f"{m.get('role', 'user')}: {c}")
    return "\n\n".join(parts) if len(parts) > 1 else (parts[0].split(": ", 1)[1] if parts else "")


def log_job(model, r):
    if not JOBLOG:
        return
    rc = r.get("receipt", {})
    line = json.dumps({"ts": time.time(), "model": model, "job_id": r.get("job_id"), "node_id": rc.get("node_id"),
                       "prompt_tokens": rc.get("prompt_tokens"), "completion_tokens": rc.get("completion_tokens"),
                       "job_ms": r.get("_job_ms"), "receipt": rc,
                       "verification_status": "not_performed", "proof_level": 0}) + "\n"
    with _joblog_lock, open(JOBLOG, "a") as f:  # one write per line under a lock: no torn lines
        f.write(line)


_node_locks = {}


def node_lock(node):
    # ponytail: one job at a time per node. The node handles one prompt at a time and, measured
    # 2026-10-11, drops prompts that arrive while it is busy (the agent then waits with no reply).
    # Queue here instead; drop this when the node accepts concurrent jobs.
    return _node_locks.setdefault(node["bootstrap"], threading.Lock())


def run_job(node, prompt, max_tokens):
    # ponytail: one process per request (~1 s libp2p setup each); a long-lived agent if throughput matters.
    # Note: --prompt is visible in `ps` to other local users; the agent has no stdin mode yet.
    cmd = [BIN, "--role", "agent", "--bootstrap", node["bootstrap"], "--model-hash", node["model_hash"],
           "--prompt", prompt, "--max-tokens", str(max_tokens), "--identity-file", IDENTITY, "--json"]
    with node_lock(node):
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        job_ms = int((time.time() - t0) * 1000)  # excludes time spent queued for the node
    # --json should print one JSON object, but the CLI also prints a log line first: take the JSON line.
    js = next((l for l in reversed(p.stdout.splitlines()) if l.startswith("{")), None)
    if p.returncode != 0 or js is None:
        raise RuntimeError((p.stderr or p.stdout)[-800:])
    r = json.loads(js)
    r["_job_ms"] = job_ms
    return r


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, headers=()):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg):
        self._send(code, {"error": {"message": msg, "type": "simon_error"}})

    def do_GET(self):
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            return self._send(200, {"object": "list", "data": [
                {"id": m, "object": "model", "owned_by": "simon", "model_hash": n["model_hash"]} for m, n in NODES.items()]})
        if self.path == "/health":
            return self._send(200, {"status": "ok", "models": list(NODES)})
        self._err(404, "not found")

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            return self._err(404, "not found")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._err(400, "invalid JSON")
        if req.get("stream"):
            return self._err(400, "streaming is not supported yet: set stream=false")
        node = NODES.get(req.get("model"))
        if not node:
            return self._err(404, f"unknown model {req.get('model')!r}; see /v1/models")
        prompt = to_prompt(req.get("messages") or [])
        if not prompt.strip():
            return self._err(400, "empty messages")
        t0 = time.time()
        try:
            r = run_job(node, prompt, int(req.get("max_tokens") or 512))
        except subprocess.TimeoutExpired:
            return self._err(504, "SIMON job timed out")
        except Exception as e:  # node unreachable, verification failure, etc.
            return self._err(502, f"SIMON job failed: {e}")
        if not r.get("receipt_zweryfikowany"):
            return self._err(502, "receipt did not verify — answer withheld")
        rc = r.get("receipt", {})
        out = {
            "id": "chatcmpl-" + uuid.uuid4().hex[:24], "object": "chat.completion", "created": int(t0),
            "model": req.get("model"),
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": r.get("output", "")}}],
            "usage": {"prompt_tokens": rc.get("prompt_tokens"), "completion_tokens": rc.get("completion_tokens"),
                      "total_tokens": (rc.get("prompt_tokens") or 0) + (rc.get("completion_tokens") or 0)},
            "simon": {
                "job_id": r.get("job_id"), "node_id": rc.get("node_id"), "runtime": rc.get("runtime"),
                # Three separate claims; a valid signature is not a verified computation.
                "execution_status": "completed",
                "receipt_status": "signature_valid_output_bound",
                "verification_status": "not_performed",
                "proof_level": 0,
                "proof_note": "the node's key signed this exact output for this job; "
                              "this does NOT prove which model or precision ran",
                "receipt": rc,
                "client_observed_ms": int((time.time() - t0) * 1000),
                "receipt_hash": (r.get("obserwacja_klienta") or {}).get("receipt_hash"),
            },
        }
        log_job(req.get("model"), r)
        self._send(200, out, headers=[("x-simon-job-id", str(r.get("job_id"))),
                                       ("x-simon-node-id", str(rc.get("node_id")))])

    def log_message(self, fmt, *args):  # no prompt content in logs, just the request line
        print(f"[simon-api] {self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    if not NODES:
        raise SystemExit("set SIMON_API_NODES to a nodes.json file")
    print(f"[simon-api] http://{HOST}:{PORT}  models: {', '.join(NODES)}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
