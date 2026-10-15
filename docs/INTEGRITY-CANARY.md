# Integrity canary: corrupted weights on GPUs without ECC (2026-10-15)

## The threat

GPUHammer (Lin, Qu, Saileshwar; USENIX Security 2025; arXiv:2507.08166) produced the first Rowhammer bit
flips in GPU memory: GDDR6 on an NVIDIA A6000, from user-level CUDA, with no physical access and no admin
rights. It works on a shared, time-sliced GPU, so one tenant can corrupt another tenant's model. A single
flip in the top exponent bit of one weight dropped ImageNet models from 80% to 0.1% accuracy, and the models
kept answering.

NVIDIA's mitigation is ECC (`nvidia-smi -e 1`). Our consumer cards cannot enable it: `nvidia-smi -e 1` on
the RTX 3090 returns `ECC features not supported`, and `ecc.mode.current` is `N/A` on the 3090 and the
GTX TITAN X.

**What it means for SIMON:**
- A node whose weights got corrupted keeps signing valid level-0 receipts over garbage. The receipt only
  says who signed the output (`docs/THREAT-MODEL.md`).
- That node is a **victim, not a cheater**. Any future penalty triggered by bad outputs would punish it.
- SIMON itself never runs third-party CUDA on a node. The node only calls its own inference server. The risk
  comes from what else shares the GPU.

## Measurement

**Setup:**
- Model: Qwen2.5-3B-Instruct Q8_0.
- Backend: llama.cpp `571d0d5`.
- Probe: 8 prompts whose first answer word is unambiguous ("anchors"): Paris, 7, Thursday, H2O, F, Jupiter,
  April, cold. Greedy decoding, 8 tokens each.

**Honest backend, no corruption:**
- 16/16 runs hit all 8 anchors: idle, under concurrent load, on the GTX TITAN X, and on CPU.
- The runs are **not** bit-identical. Two prompts changed after their first 3–4 tokens between runs ("F, G,
  and H are eight friends…" vs "F, G, H, I, J…"), depending on batch composition.
- So the probe compares only the anchor (the first word), never the whole text.

**Simulated single-bit flips:**
- Each flip was made in a copy of the GGUF and run on CPU. The copy was restored byte-identical afterwards.
- Q8_0 stores blocks of 32 int8 weights with one fp16 scale per block.

| flip | anchors hit | effect |
|---|---|---|
| top exponent bit of one block scale, `blk.10.ffn_down` | **0/8** | total garbage |
| same, in the embedding row of a rare token (the output head is tied to it) | **2/8** | garbage in every answer |
| sign bit of one int8 weight, `blk.10.ffn_down` | 7/8 | almost unchanged |
| lowest mantissa bit of a block scale | 8/8 | no visible change |
| top exponent bit of one block scale, `blk.10.attn_q` | 8/8 | **not detected**; no visible change on these prompts |

## The tool: `tools/simon-canary`

- **Verdict:** ok (8/8), warn (1–2 misses), fail (≥ 3 misses).
- **Confirmation:** a fail is re-run once at once, and only two fails in a row trigger `--on-fail`.
- **Default action:** stop the SIMON node (quarantine). A human then reloads the weights and restarts it.
- **Unreachable backend:** gives no verdict and never counts as corruption.
- **Status file:** records the backend, the model the backend reports, and a hash of the probe set.
- **Monitor:** reads the status file and shows it on the node's card on `/network`, marked self-reported.
  A status older than 30 minutes shows as stale.

```bash
python3 tools/simon-canary/simon_canary.py --backend http://127.0.0.1:18430 \
    --status ~/.simon/canary-demo.json --on-fail "systemctl --user stop simon-demo-node"
```

## What it does not do

- **It catches catastrophic corruption only.** A flip that harms only rare contexts passes; see the
  `attn_q` row above. Catching every flip needs a checksum of the weight buffers computed on the GPU. That
  is a research item in `ROADMAP.md`: weights are read-only, and all 24 GB of a 3090 read in about 25 ms.
- **It is self-reported.** The node runs it and writes the result, so it protects honest operators but does
  not expose a lying node. The probe prompts are public, so a cheater can special-case them. The protocol
  fix is hidden known-answer probes issued by verifiers and indistinguishable from real jobs (ROADMAP).
- **Its calibration covers one model and one backend.** The thresholds come from 16 honest runs on that
  setup. Other models need their own calibration run before the canary may quarantine anything.
- **It runs at intervals.** With a 10-minute timer, a corrupted node can sign wrong answers for up to
  10 minutes before it is stopped.

## Operator rules that follow

1. Do not share a node's GPU with untrusted CUDA: guest models, other people's kernels, multi-tenant rental.
2. Prefer GPUs with ECC (HBM: A100, H100; GDDR7 with on-die ECC: RTX 5090) or dedicated instances for
   nodes whose answers matter.
3. A canary fail or a gross M3 audit failure means **quarantine and re-audit, never a penalty**.
