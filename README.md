# SIMON

**Verifiable LLM inference on untrusted, heterogeneous hardware.**

SIMON is a peer-to-peer harness that dispatches inference jobs to nodes nobody
controls centrally, and then makes the result *checkable*: every job produces an
Ed25519-signed receipt, and any verifier can re-run a single forward pass over
`prompt + output` to audit what the node claimed it computed.

The hard question is not "can we distribute inference" — it is **"how do you
punish a lying node without punishing an honest one?"** That is the question
this repository is actually about, and most of the work here is measurement
rather than architecture.

**Try it:**
- [Tamper, then verify](https://pop-os.tailaf1556.ts.net/simon/demo): change a node's answer and watch
  the receipt get rejected. The check runs in your browser, using the same Rust verifier as the CLI, compiled to WebAssembly.
- [Network](https://pop-os.tailaf1556.ts.net/simon/network): live node cards and the job feed, with every
  receipt's signature checked in your browser. It shows data only while our demo node is up, never sample data.
- `przyklady/README.en.md`: verify a real receipt offline with one command.

---

## Status

Working, measured, and openly incomplete. Nothing below is projected — every
number was produced on our own machines and the raw data lives in the repo.

| Component | State |
|---|---|
| libp2p transport (gossipsub + request/response, CBOR) | working |
| Ed25519 job receipts | working |
| Admission control (C+1 gate) with real tokenizer counts | working |
| Chunking + hierarchical map-reduce for over-context jobs | working |
| Agent↔agent orchestration (job B consumes job A's output) | working |
| OpenAI-compatible API gateway (`tools/simon-api`): each completion is a real SIMON job with its receipt | working |
| Network monitor (`/network` page + `tools/simon-monitor`) | working |
| AMD ROCm node (MI300X) | working, measured — see below |
| Slashing rules for dishonest nodes | **unresolved — see below** |

Platforms proven end-to-end: **Linux (CUDA)**, **Linux (ROCm, AMD Instinct MI300X)** and
**macOS on Intel x86_64**, including cross-platform interop between them.

The Mac is a **2012 Core i7** — which is the point. On 18 September 2026 a
receipt issued by an RTX 3090 was verified on that laptop: `RECEIPT VALID`,
then `REJECTED` after one extra space was appended to the answer. No GPU, no
network, no trust in whoever handed over the files. Reproduce it yourself with
`examples/` below. Apple Silicon and big-endian targets remain unverified, and
we do not claim them. `docs/PAZUR-macos-bringup.md` is the runbook (Polish).

## What a receipt proves — and what it does not

Stating this precisely matters more than stating it favourably.

A receipt today proves exactly: **a registered node signed this exact answer as
the result of this job.** The signature covers a commitment to the output text
bound to the job id, so substituting the answer, tampering with it in transit,
or pairing a valid receipt from another run with this text are all rejected.

It does **not** prove that the declared model generated that answer. A malicious
node can sign arbitrary text together with a correctly computed digest. Binding
`model + prompt + execution + output` requires an execution audit (TopLoc), and
that is not implemented.

| | |
|---|---|
| Output binding | implemented + tested |
| Token fields signed | implemented |
| Token counts independently recomputed | partial — verify separately |
| Execution correctness | **not implemented** |
| Economic credit | **not implemented** |
| Wash-compute resistance | **unsolved** |

The token counters are the node's signed *declaration*: the signature stops
them being changed afterwards, it does not make them true. The same holds for
the reported timings — only round-trip latency is measured independently, so
**settlement must never rest on node-reported time**. `docs/SECURITY-LOG.en.md`
records the previous behaviour of each fix, not just the fix.

## Measured results

**Audit cost.** An audit is `prefill(N+M)`; the job itself is
`prefill(N) + decode(M)`. Decoding is ~55× slower per token, so auditing is
cheap:

| prompt | output | job | audit | audit as % of job |
|---:|---:|---:|---:|---:|
| 500 | 50 | 7.9 s | 0.63 s | 8.0% |
| 2016 | 200 | 18.8 s | 1.86 s | 9.9% |
| 2011 | 500 | 87.1 s | 2.07 s | 2.4% |
| 6037 | 500 | 69.1 s | 5.12 s | 7.4% |

**2.4–9.9% of the job, median 7.4%.** This is the number that decides whether
verification can be paid for out of the job price. It can.

**Honest drift.** Before you can slash a node for a mismatched fingerprint, you
must know how much two *honest* runs differ. We measured it. On identical
hardware the token sequence was stable and logprob deltas were tiny — but we
explicitly **withdrew** two stronger claims we had first drawn from that data,
because the measurement could not support them (see
`docs/design/DESIGN-VERIFIER-0.md`). A cross-hardware run came back
bit-identical, which is a *confounded* negative result, not a green light.

**Therefore: a fingerprint mismatch is currently treated as a reason to
re-audit, not as proof of fraud.** Automatic slashing is not enabled, and we say
so rather than shipping a threshold we cannot defend.

## Why this matters for AMD

SIMON's entire value proposition is running on hardware that is *not* uniform —
whatever GPU a volunteer happens to own. But our verification work so far has
been proven on NVIDIA/CUDA and an Intel Mac only, for the mundane reason that
those are the machines we have.

That is a real gap, and it is precisely where the interesting question lives:
**numerical reproducibility across vendors.** If an honest AMD node and an
honest NVIDIA node compute measurably different activations for the same input,
then any naive fingerprint comparison slashes honest participants — and every
cross-vendor decentralized inference network has this problem whether or not it
has noticed yet.

We measured it on ROCm rather than speculate about it (AMD Developer Cloud, 1× MI300X,
2026-10-11; full write-up and raw data in `docs/AMD-MI300X-RESULTS.md`):

- **Cross-vendor false positives:** in the pre-registered test, an honest MI300X flagged the **same 5 of 32
  prompts** as the NVIDIA reference checked against itself. Its output was byte-identical on 22/32. The vendor
  adds no false positives for this model and metric; the noise comes from the verification regime.
- **SIMON node on AMD:** Qwen3.8-27B on the MI300X, reached through the OpenAI-compatible
  gateway from Poland. Receipts verify, and a single changed byte is rejected.
- **Capacity:** one MI300X sustained **64 concurrent streams** of Qwen3.8-27B (BF16, vLLM). All 192
  requests stayed within TTFT ≤ 3 s and ≥ 10 tok/s per stream, at ~2000 tok/s in total.
- **SIMON layer cost:** the same 64 streams sent through a SIMON node ran at the same ~2000 tok/s. All 510
  jobs (1–64 streams) came back with a verified receipt; one job costs ~14 ms more than vLLM alone.
- **Routing, not sharding:** splitting one model across a MI300X and a 3090 over the internet ran 12×
  slower, and remote MoE experts 55× slower. Separate whole-model nodes gave lower latency, not more
  throughput. SIMON therefore routes whole jobs and splits a model only when it does not fit.

## Build

```bash
cargo build --release
```

Rust workspace, no external services required to build. Running a node
additionally needs an OpenAI-compatible inference server (we use vLLM on Linux,
llama.cpp elsewhere).

```bash
# a node in front of any OpenAI-compatible backend
simon --role node --listen /ip4/0.0.0.0/tcp/9001 --model-url http://127.0.0.1:8000 \
      --model-hash my-model --key-file node.key
# OpenAI-compatible API in front of SIMON nodes (stdlib Python); jobs logged for the monitor
SIMON_API_NODES=nodes.json SIMON_API_JOBLOG=jobs.jsonl python3 tools/simon-api/simon_api.py
# read-only monitor JSON for the /network page
SIMON_MONITOR_CONFIG=monitor.json SIMON_API_JOBLOG=jobs.jsonl python3 tools/simon-monitor/simon_monitor.py
```

The file formats are documented at the top of each script.

## Documentation

- `docs/whitepaper/SIMON-Whitepaper-EN.pdf` — full write-up (EN; PL version alongside)
- `docs/design/DESIGN-VERIFIER-0.md` — verifier economics, drift measurements, open questions *(Polish)*
- `ROADMAP.md` — what is done, what is blocked, and by what *(Polish)*
- `przyklady/README.en.md` — a real receipt you can verify offline in one command
- `docs/AMD-MI300X-RESULTS.md` — the MI300X measurements: cross-vendor false positives, node + API, throughput, MoE, concurrency
- `docs/SECURITY-LOG.en.md` — every fix with the behaviour it replaced, and the current status table
- `docs/PAZUR-macos-bringup.md` — the macOS bring-up runbook, including the traps *(Polish)*
- `notebooks/SIMON-D2-ROCm.ipynb` — the cross-vendor measurement itself, runnable on
  AMD Developer Cloud; the CUDA baseline is embedded, so it reports a verdict in-session

## Licence

MIT.
