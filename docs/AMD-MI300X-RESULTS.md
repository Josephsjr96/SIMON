# SIMON on AMD Instinct MI300X — results (2026-10-11)

Everything here ran on one AMD Developer Cloud droplet: 1× MI300X (192 GB, gfx942),
the vLLM Quick Start image, ROCm 7.2.3. The client was in Poland, about 124 ms round trip from the
datacenter in Atlanta.

- **Raw data:** `docs/amd-data/`.
- **Benchmark clients:** `tools/simon-bench/`.
- **Versions:** `docs/amd-data/droplet-versions-2026-10-11.txt`. llama.cpp is at `571d0d540` on every machine, vLLM is
  `0.27.1+rocm723`, and the model checksums are listed there.

## 1. Cross-vendor false positives (pre-registered M3 rule)

The question: does an honest AMD node look like a cheater to an NVIDIA verifier?

- **Setup:** Qwen2.5-3B-Instruct Q8, a byte-identical GGUF on both sides (sha256 `12491ec9…`). Same llama.cpp
  commit and flags. 32 prompts, metric `contain2`, threshold 0.02 (`docs/FP-PREREGISTRATION.md`).
- **Result:**

  | config | flagged prompts | mean suspicious |
  |---|---|---|
  | NVIDIA RTX 3090 checked against itself | 5/32 | 0.0312 |
  | AMD MI300X | 5/32 | 0.0312 |

- **Detail:**
  - The flagged prompts are identical on both: 3, 4, 10, 25, 27.
  - AMD's greedy output is byte-identical to NVIDIA's on 22/32 prompts. The other 10 differ only at tokens the NVIDIA reference itself
    ranks in its top 2.
- **Conclusion:** for this model and metric, an honest AMD node adds **no false positives** beyond NVIDIA's own
  self-check. The false positives come from the verification regime (5/32) and from legal KV-cache
  quantization (26/32), not from the vendor.
- **The verdict is still FAIL**, because honest configurations flag prompts, so M3 stays telemetry
  (`docs/FP-RESULT.md`).
- **Scope:** one 3B model, Q8, llama.cpp, a 20-token window.

Raw data: `simon-fp-amd-mi300x-2026-10-11.jsonl`.

## 2. A SIMON node on the MI300X, behind an OpenAI-compatible API

- **Setup:**
  - Qwen3.8-27B (BF16 on vLLM, then Q8 on llama.cpp) served on the MI300X.
  - `simon --role node` runs on the droplet; the client harness runs in Poland.
  - The gateway, `tools/simon-api`, turns each OpenAI chat completion into one SIMON job and returns the
    receipt next to the answer.
  - Tested with curl and with the OpenAI SDK.
- **Result:** every receipt verified offline: `RECEIPT VALID`.
  - Changing one byte of the answer gave `REJECTED` (output does not match).
  - Changing one signed field gave `REJECTED` (bad signature).
- **Scope:** this authenticates the worker's receipt and detects tampering. It does **not** prove which model ran
  (proof level 0).

## 3. Throughput: whole model vs split vs separate nodes (Qwen3.8-27B)

Method: streaming, client-side timing, medians of 3 runs, 256 output tokens.

### Round 1

| setup | TTFT | tok/s per request | total tok/s |
|---|---|---|---|
| A: MI300X, whole model Q8, 1 request | 654 ms | 67.4 | 57.3 |
| A: MI300X, 4 parallel | 893 ms | 44.1 | 151.8 |
| B′: same MI300X, model split over llama.cpp RPC via loopback | 656 ms | 60.6 (−10%) | 52.6 |
| RTX 3090, whole model Q4_K_M, local | 217 ms | 42.6 | 41.3 |
| D: one model across MI300X + 3090 over the internet (3% of layers on the 3090) | 9 409 ms | 5.6 | 4.1 |

### Round 2: matched quantization, 4 streams

The same Q4_K_M file on both cards (sha256 `322e194f…`), with the same server flags. Round 1 had compared Q8 on AMD with Q4 on the
3090; that mismatch made "separate nodes beat one node" look true. At matched quantization it is not.

| setup | total tok/s | per stream | TTFT p50 / p95 | within limits |
|---|---|---|---|---|
| A: MI300X, 4 streams | **146.3** | 45.4 | 1389 / 1394 ms | 12/12 |
| C′: MI300X 2 streams + 3090 2 streams, separate nodes | 129.4 | 56.3 / 35.8 | 784 / 1001 ms | 12/12 |
| RTX 3090 alone, 4 streams | 87.9 | 25.2 | 1543 / 1692 ms | 12/12 |

The limits were fixed before the run (our pilot criteria): TTFT ≤ 3 s and ≥ 10 tok/s per stream.

**What it shows:**
- Separate nodes give lower TTFT, not more total throughput; the slower card sets the pace.
- Splitting one model through llama.cpp RPC costs ~10% even without a network.
- Over the internet, splitting runs 12× slower, because every token waits on the remote layers.
- SIMON's design follows from this: **route whole jobs to nodes; split a model only when it does not fit.**

## 4. MoE experts across nodes (Qwen3-30B-A3B Q8)

The experts of layers 46–47 were moved to another device with `--override-tensor`.

| setup | TTFT | tok/s per request | total tok/s |
|---|---|---|---|
| M1: whole MoE on the MI300X, 1 request | 592 ms | 175.6 | 125.1 |
| M1: 4 parallel | 526 ms | 110.9 | 357.8 |
| M2a: those experts via loopback RPC (same GPU) | 516 ms | 164.7 (−6%) | 125.9 |
| M2b: those experts on an RTX 3090 in Poland (124 ms RTT) | 4 447 ms | 3.2 | 2.9 |

**What it shows:**
- Each layer with remote experts costs about one round trip per token.
- Synchronous, per-token expert parallelism over the internet does not work for interactive generation.
- This does not rule out asynchronous work, other batching, or other distributed designs. Expert
  parallelism belongs inside one machine or pod with a fast interconnect; a multi-GPU MI300X pod was
  not available to this account, so that case is unmeasured.

## 5. One MI300X, many concurrent streams

Qwen3.8-27B, ~55-token prompts, 256 output tokens, a unique prefix per request (no prefix-cache
hits). Same limits as above. These are two **deployment configurations**, not an engine
comparison: the precision and server settings differ.

| config | streams | total tok/s | per stream | TTFT p50 / p95 | within limits |
|---|---|---|---|---|---|
| vLLM 0.27.1, BF16 | 1 | 57.2 | 66.0 | 600 / 609 ms | 3/3 |
| | 4 | 199.5 | 56.6 | 571 / 633 ms | 12/12 |
| | 16 | 679.0 | 47.4 | 607 / 702 ms | 48/48 |
| | 32 | 1254.1 | 43.3 | 594 / 648 ms | 96/96 |
| | 64 | **1998.8** | 34.5 | 687 / 798 ms | **192/192** |
| llama.cpp Q8 (`-np 32`) | 1 | 55.0 | 66.4 | 817 / 820 ms | 3/3 |
| | 4 | 95.8 | 27.2 | 1324 / 1327 ms | 12/12 |
| | 16 | 140.4 | 13.2 | 5097 / 18867 ms | 16/48 |
| | 32 | 156.8 | 16.3 | 36680 / 36801 ms | 0/96 |

> One MI300X sustained **64 concurrent streams** of Qwen3.8-27B (BF16, vLLM 0.27.1). All 192 requests
> met TTFT ≤ 3 s and ≥ 10 tok/s per stream, measured from Poland, with ~2000 tok/s in total.

**Caveats:**
- The cap at 64 is our `--max-num-seqs` setting, not the latency limits; higher concurrency was not measured.
- llama.cpp in this configuration scales poorly with concurrency. That was not debugged, so capacity claims rest on the vLLM column.

## Pitfalls worth knowing

- **The vLLM Quick Start image publishes container port 8000 on all interfaces.** A scanner found it within
  minutes. Block it before starting vLLM: `iptables -I DOCKER-USER -i eth0 -p tcp --dport 8000 -j DROP`.
- **Qwen3.8 on vLLM** needs `--reasoning-parser qwen3`, or the thinking ends up in the answer.
  - The model is a hybrid (Mamba layers), so vLLM also needs `--max-num-seqs` below the number of Mamba cache blocks.
- **Qwen3.8 on llama-server:** `--reasoning-budget 0` does not stop thinking; `--chat-template-kwargs '{"enable_thinking":false}'` does.
- **llama.cpp RPC:**
  - Build both sides with `-DGGML_RPC_RDMA=OFF`; a mismatch hangs the handshake.
  - The RPC device counts first in `-ts`.
  - An `-ot` buffer name must include the address (`RPC0[host:port]`).
