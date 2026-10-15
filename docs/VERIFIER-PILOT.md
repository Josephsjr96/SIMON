# Which model does a node serve? Verifier pilot (2026-10-14/15)

A SIMON receipt shows which node signed an output. It does not show which model produced the output. This
pilot measures a statistical answer to the second question. It is a pilot with a small number of samples. It
is not a proof and not a published error rate.

- Code: `tools/simon-lidar/` (`lidar.py`, `onetoken.py`).
- Raw data: `docs/verifier-data/` (`refs-*.jsonl` for layer 1, `ot-*.jsonl` for layer 2).
- Path: every request went through the SIMON gateway and a SIMON node. Each agent step was a SIMON job with
  an Ed25519-signed receipt that the client verified.

## The two layers

1. Agent behavior (`lidar.py`), after LIDAR (Tsinghua University, arXiv:2609.28559). An agent with tools
   runs 3 small coding tasks in A/B variants: verify (fix a bug, with and without "run the tests"), recover
   (the first test run fails on purpose), resolve (one test contradicts the specification). About 190
   features describe each fingerprint of 6 runs. A class profile uses Jeffreys smoothing. The verdict is
   open-set: `consistent`, `inconsistent` or `inconclusive`. The authors of LIDAR did not release code,
   tasks or fingerprints, so the tasks and references here are our own.
2. Single-token distributions (`onetoken.py`), after Bruckner, "One Token Is Enough" (arXiv:2607.10252).
   10 one-word questions (random number, letter, word, color, animal, city, coin flip, favorites) in English
   and Polish, 30 samples per cell at temperature 1.0. The distance is the mean Jensen-Shannon divergence
   over the 20 cells. We compare half-samples to half-samples, so the sample size is equal on both sides.

## Setup

| Class | Weights | GPU | Layer 1 fingerprints | Layer 2 fingerprints |
|---|---|---|---|---|
| `lfm2.5-1.2b-q4` | LFM2.5-1.2B-Instruct Q4_K_M (other family) | CPU | 6 | 4 |
| `qwen2.5-0.5b-q4` | Qwen2.5-0.5B-Instruct Q4_K_S | GTX TITAN X | 6 | 4 |
| `qwen2.5-3b-q8` | Qwen2.5-3B-Instruct Q8_0 | GTX TITAN X | 6 | 4 |
| `qwen2.5-3b-q8-3090` | the same file | RTX 3090 | 10 | 4 |
| `qwen2.5-3b-q4` | Qwen2.5-3B Q4_K_M, quantized by us from the Q8_0 file | GTX TITAN X | 6 | 4 |
| `qwen2.5-7b-q8-3090` | Qwen2.5-7B-Instruct Q8_0 | RTX 3090 | 10 | 4 |
| `qwen2.5-14b-q8-3090` | Qwen2.5-14B-Instruct Q8_0 | RTX 3090 | 10 | 4 |

All backends: llama.cpp `571d0d54`, `--jinja`, default sampler. Fixed agent sampling: temperature 0.7, top_p
0.9. Bielik-Minitron-7B was in the first plan. Its chat template in llama.cpp does not produce tool calls,
so it wrote only text in all 15 steps. That compares templates, not behavior, so we removed it.

Fingerprints with an endpoint error are dropped and counted. 4 of 54 layer-1 fingerprints were dropped:
a malformed tool call from LFM that the llama.cpp parser refused, a context overflow in llama.cpp, a failed
connection to llama.cpp, and one request that the context gate of the node refused. The overflow showed a
gap in the node: llama.cpp does not report `max_model_len`, so the context gate was off. The node now reads
the slot context size from `/props`. After this fix, the gate refused the 0.5B request (8762 tokens, limit
8192) with a controlled error.

## Results

Layer 1, leave-one-fingerprint-out, with the 3B Q8 fingerprints from both GPUs in one class: 46 of 50 top-1.

| True class | Predicted | Open-set verdicts for honest fingerprints |
|---|---|---|
| lfm2.5-1.2b-q4 | 5 of 5 correct | 5 consistent |
| qwen2.5-0.5b-q4 | 5 of 5 correct | 5 consistent |
| qwen2.5-3b-q8 (TITAN X and 3090) | 16 of 16 correct | 16 consistent |
| qwen2.5-3b-q4 | 0 of 4 correct (3 as 3B Q8, 1 as 14B) | 4 inconclusive |
| qwen2.5-7b-q8-3090 | 10 of 10 correct | 10 consistent |
| qwen2.5-14b-q8-3090 | 10 of 10 correct | 9 consistent, 1 inconclusive |

No honest fingerprint got the verdict `inconsistent`.

Layer 2, Jensen-Shannon distance between fingerprints (min to max over all pairs):

| Pair | Distance |
|---|---|
| same class, 14B Q8 | 0.076 to 0.105 |
| same class, 7B Q8 | 0.093 to 0.131 |
| same class, 3B Q8 (one GPU) | 0.191 to 0.231 |
| 3B Q8 on TITAN X against 3B Q8 on RTX 3090 | 0.201 to 0.245 |
| same class, 3B Q4 | 0.233 to 0.273 |
| same class, LFM 1.2B | 0.309 to 0.364 |
| same class, 0.5B | 0.423 to 0.494 |
| 3B Q4 against 3B Q8 (same weights) | 0.426 to 0.512 |
| 14B against 7B | 0.493 to 0.533 |
| 3B against 7B | 0.517 to 0.627 |
| LFM against Qwen | 0.64 to 0.80 |

## What the pilot shows

| Question | Layer 1 (agent behavior) | Layer 2 (single-token) |
|---|---|---|
| Other family (LFM against Qwen) | separates | separates |
| Other size (0.5B, 3B, 7B, 14B) | separates | separates |
| Same weights, other quantization (Q4 against Q8) | does not separate | separates |
| Same weights and quantization, other GPU | one class (no false alarm) | inside the same-class range (no false alarm) |

1. The layers complement each other. Layer 1 identifies family and size. Layer 2 also detects a quantization
   change. Cai et al. ("Are You Getting What You Pay For?") report that behavior and embedding classifiers do
   not separate Q8 from Q4, and layer 1 agrees.
2. A change of GPU did not cause a false alarm in this pilot. The same weights on a GTX TITAN X and an RTX
   3090 gave one class in layer 1 and a distance inside the same-class range in layer 2.
3. A global threshold does not work for layer 2. The same-class spread depends on the model: 0.08 for 14B,
   0.49 for 0.5B. Calibrate the threshold for each declared model on its honest fingerprints. For 3B Q8, the
   largest same-model distance was 0.245 and the smallest other-model distance was 0.426.

## Limits

1. The sample is small: 4 to 10 fingerprints per class. These numbers do not give an error rate.
2. Our 3B Q4 file comes from the Q8_0 file, not from full-precision weights. This can make the Q4 difference
   larger than for a Q4 file from the original weights.
3. All runs used one engine (llama.cpp) and its default sampler. Layer 2 detects a different configuration
   (weights, quantization, engine, sampler), not only different weights. A node that changes its engine will
   show a distance, and a verifier must not call that fraud without a check.
4. The tasks and questions are public and fixed. A dishonest node can detect them and answer like the
   declared model. A production verifier needs a secret, rotating set of tasks and probes that look like
   normal traffic.
5. A node can serve the declared model for probes and another model for other jobs. Probes must be
   indistinguishable from client jobs.
6. The harness and the tasks are ours. The numbers do not compare with the LIDAR paper.

## Reproduce

```bash
python3 tools/simon-lidar/lidar.py eval --refs docs/verifier-data/refs-*.jsonl
python3 tools/simon-lidar/onetoken.py eval --refs docs/verifier-data/ot-*.jsonl
```

The first command keeps the TITAN X and the RTX 3090 3B Q8 fingerprints as two classes, so it shows the
confusion between them. To use one class, give both files the label `qwen2.5-3b-q8`.
