# M3 false-positive result — pre-registered rule returned **FAIL**

Rule: `docs/FP-PREREGISTRATION.md` (committed before measuring). Metric = `contain2` (the
shipped metric), unit = one prompt text, `max_poza = 0.02`, `k = 2`, `max_margin = 0.25`.

## Run

- Model: Qwen2.5-3B-Instruct Q8 (same GGUF everywhere; tokenizers verified identical).
- Reference: 3B on RTX 3090 (`-ngl 99`, KV f16, default `-b`).
- 32 distinct prompts, 20 greedy tokens each; each config generates its OWN trajectory; the
  reference teacher-forces it; `seq_hash` recorded per row.
- Configs executed: `ref`, `cpu` (CPU only), `cpu_b512` (CPU, `-b 512 -ub 128`), `kv_q4`
  (3090, KV cache `q4_0`).

| config | flagged prompts | mean suspicious |
|---|---|---|
| **ref** (reference checked against itself) | **5/32** | 0.0312 |
| cpu (different backend) | 5/32 | 0.0312 |
| cpu_b512 (batching) | 6/32 | 0.0328 |
| kv_q4 (cache quantization) | **26/32** | 0.1437 |
| amd_mi300x (ROCm/HIP, added 2026-10-11) | 5/32 — the same 5 prompts as `ref` | 0.0312 |

**AMD arm (2026-10-11):** an honest MI300X adds no false positives beyond the reference's own
self-check; output byte-identical to NVIDIA on 22/32 prompts. Details: `docs/AMD-MI300X-RESULTS.md`.

## Verdict (per pre-registration)

**FAIL.** The rule was: PASS only if **no honest configuration flags any prompt**. The
**reference configuration flags 5/32 of its own prompts**, and a legitimate operator choice
(KV cache `q4_0`) flags 26/32.

Therefore, per the pre-registration: **M3 in its current form (20-step window, threshold
0.02) is not a detector.** In this configuration it stays telemetry only and does not trigger
escalation. Slashing is already off (`m3::decyzja` cannot emit `HardFail`). The receipt layer
is unaffected and remains the product.

This is a statement about this configuration, not about the approach: the 20-step window
cannot resolve anything finer than one token, so the honest next research question (after the
hackathon) is the noise floor as a function of window length, and verifying in the same mode
the node generated in.

## Why `ref` flags itself

The node generates with `gen_reference` (batched `n_predict=20`, `cache_prompt=false`); the
verifier scores with `force_eval` (incremental, `cache_prompt=true`). The same weights under
two inference regimes agree on top-1 at most steps but diverge at near-tie steps; one such
step in 20 (`1/20 = 0.05 > 0.02`) flags the prompt. So the shipped threshold sits **below the
inference-regime noise floor** — the "one token in twenty" problem the reviewer predicted.

## Limitations / next

- 6 of the 11 pre-registered configs not yet run: `kv_q8`, partial `-ngl`, flash-attn,
  older commit, `-np 4` parallel load, Vulkan. (ROCm/HIP on MI300X ran on 2026-10-11, above.)
- Blocker on the 3090: a separate MiMo-V2.6 Q8 server holds ~15 GB (not disturbed); the GPU
  arms that need more than one 3B at a time must run sequentially or after it is idle.
- **No AUROC is published** (pre-registration). Any further M3 work is blocked until the
  matrix is complete; the current evidence already says M3 is not a detector.

## Publishable (honest)

> "On 32 prompts, our own reference configuration flagged 5/32 under our shipped threshold,
> and a legitimate KV-cache quantization flagged 26/32. **M3 in its current form (20-step
> window, threshold 0.02) is not a detector**; in this configuration it remains telemetry. Our
> receipts prove authorship and binding, not execution."
