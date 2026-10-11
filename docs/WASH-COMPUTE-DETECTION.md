# Wash-Compute Resistance: Measure Deterrence and Detection Together

**Status:** Research proposal, revision 2. No implementation yet.
**Author:** Yousef Sanjari (Joe)
**Date:** 2026-10-11
**Context:** SIMON, verifiable LLM inference on untrusted, heterogeneous hardware

**Revision 2 changes:** deterrence and detection are now treated as complementary (§1.1); the evaluation is against an adaptive attacker with grouped splits (§4, §5); the data plan uses public workload traces and a simulated SIMON market instead of the demo Worker (§3); privacy handling is stricter (§3.3); the "first dataset" claim is removed (§2.2); scope is moved to after the 18 October submission (§9).

---

## 1. The Problem

SIMON's README states it plainly:

> **Wash-compute resistance: unsolved**

A receipt proves that a registered node signed an exact answer as the result of a job. It does **not** prove that the job was demanded by a real user.

In SIMON, wash-compute means a node (or a coalition) sends jobs to itself. Receipts are valid and audits can pass, because the work really was done, for the attacker. Verification therefore cannot detect it. When client and executor have the same owner, the payment returns to that owner, and the real cost is electricity plus protocol and verifier fees. If whatever the protocol pays out is worth more than that, self-dealing stays rational.

An owner can also split into many identities (Douceur's Sybil attack, applied to the demand side), so detection by identity alone fails.

### 1.1 Channels through which wash-compute can pay

1. **Emission per unit of work.** Blocked by design today (README, roadmap).
2. **Reputation or allocation.** Allocation proportional to measured power lets a wash trader buy a larger share of real client jobs.
3. **Build then cheat.** Cheap self-dealt jobs build a clean audit history, followed by cheating on one valuable job.
4. **Metric inflation.** Job counts and tokens served look like demand and are not.

### 1.2 Deterrence and detection are complementary

Deterrence fixes the economics: for any coalition, what it can extract from a job should be at most what it irrecoverably paid for it (burned fees, verifier fees, real cost), however it splits into identities.

Detection does not replace that. A rational attacker will imitate honest traffic, so a detector is only worth the **extra cost it forces on an attacker who wants to evade it**. This study measures that cost. The detector's output is a risk score that feeds re-audit and review. It never triggers slashing.

---

## 2. Hypothesis and Contribution

### 2.1 Hypothesis

> A detector trained on honest demand and on naive wash-compute loses most of its power against an adaptive attacker. How quickly it loses power, as a function of attacker budget, is measurable and decides how much weight a detector may carry in SIMON.

This is falsifiable: if detection power stays high as attacker budget grows, the detector is a stronger defense than expected.

### 2.2 Contribution

Not a new cryptographic mechanism and not a claim to the first workload dataset. Public LLM serving traces already exist (BurstGPT, the Azure LLM inference traces, LMSYS-Chat-1M). They are the honest baseline here.

The contribution is:

- a **simulation** of a SIMON-like market showing under which parameters self-dealing has non-positive expected value;
- **labeled wash-compute traffic** in that simulation, from naive to adaptive attackers;
- a **detection-versus-evasion-cost curve**.

A literature check on wash-trading detection (including NFT and DePIN work) is a prerequisite before any novelty claim is written down.

---

## 3. Data Plan

### 3.1 Honest class

Public traces, used for the **marginals** of honest traffic: arrival times, daily and weekly periodicity, prompt and output token-length distributions. Per their published descriptions, these traces do not carry per-user identities, so simulated honest "users" are sampled from the trace distributions. That limitation is stated in the results.

### 3.2 Simulated market (Part A) and wash class

Agent-based simulation with clients, executors and verifiers, a payment ledger, burned fees, and an allocation rule (proportional to power, as in the design). Wash strategies are agents that choose job mix, identity splits and verifier roles.

Optional pilot: the demo Worker may log request metadata for sanity checks only. Its traffic is small (40 requests per hour per throttle) and dominated by judges and bots, so it is **not** used for training or for any claim about demand.

### 3.3 Privacy constraints

- No raw IPs, prompts or outputs stored.
- Requester IDs: **keyed hash (HMAC) with a rotating secret** and a fixed retention limit. An unkeyed hash of an IPv4 address is trivially reversible, and pseudonymized data is generally still personal data under the GDPR.
- Prompt similarity via **MinHash or SimHash sketches** (near-duplicate detection without storing text), not plain hashes.
- Publish only aggregates or synthetic data. Have the legal basis, retention and publication plan reviewed by someone qualified before any real logging starts.

---

## 4. Attack Generation

Static attacks (the original five):

| Attack | Simulation |
|---|---|
| Self-demand | Same ID submits rapid, repetitive jobs |
| Sybil demand | Multiple IDs submitting identical prompts |
| Low-diversity | Fixed prompt, varying only output length |
| Burst | Spikes at predictable intervals |
| Churn | New IDs appearing and disappearing rapidly |

Adaptive tiers (the attacker knows the feature set):

| Tier | Evasion |
|---|---|
| A1 | Timing jitter |
| A2 | LLM-generated diverse prompts |
| A3 | Many identities, rotating network addresses |
| A4 | Samples sizes and timing from the honest trace marginals |
| A5 | Pairing-aware: spreads work across many executors and uses intermediaries to hide client-executor concentration |

Each tier has an attacker **cost** (extra compute, fees, latency, number of identities), recorded alongside the label.

---

## 5. Classifier and Evaluation

### 5.1 Features

Features that exist in SIMON's protocol (graph and flow), not web-traffic features:

- **Pair concentration:** share of a client's jobs going to its top executor (Herfindahl index)
- **Net external inflow:** value entering a cluster from outside versus value circulating inside
- **Cycle closure rate:** payments returning to the cluster that sent them
- **Counterparty latency:** round-trip time between client and executor
- **Timing correlation** between payment and job events
- **Hardware fingerprint equality** between client and executor
- **Near-duplicate prompt rate** (MinHash)
- Request rate and time-of-day concentration per identity

### 5.2 Models

Rule-based baseline, logistic regression (interpretable), XGBoost.

### 5.3 Evaluation protocol

- **Grouped splits:** no coalition or identity appears in both train and test.
- **Leave-one-attack-out:** train on some attack types, test on the held-out one.
- **Metrics:** PR-AUC and recall at fixed false positive rates (1%, 0.1%), because wash traffic is a small share of real traffic. F1 on balanced data is not reported as the headline.
- **Headline result:** detection recall versus attacker cost for tiers A0 to A5.

### 5.4 Output

A suspicion score from 0 to 1. It is used to prioritize manual review, weight reputation and flag receipts for re-audit. **Never** slashing.

---

## 6. Part A: Economic Simulation

Sweep reward-to-burn ratio, audit rate, stake weighting and fees. Find the region where the best coalition strategy has non-positive expected value. Include an adversary that selects the job class with the highest reward per unit of cost, which tests the unit-of-work pricing (prefill versus decode, cached tokens).

---

## 7. Limitations

- **Simulation is not a network.** Results transfer only as far as the simulated incentives match SIMON's.
- **Trace marginals are not user sessions.** Honest users are synthetic.
- **The adaptive attacker is imagined by the author.** Stronger attackers may exist.
- **Detection is an arms race.** Retraining is required if it is ever deployed.
- **Fees that deter wash-compute also tax honest users.** The result is a trade-off, not a free fix.
- **No production validation.** This is a research proposal.

---

## 8. Deliverables

1. `docs/WASH-COMPUTE-DETECTION.md` (this document)
2. `sim/` wash-compute market simulation (parameters, attackers, results)
3. `notebooks/wash_compute_detection.ipynb` training and evaluation
4. A short write-up suitable for arXiv or a technical blog post
5. Optional: `worker/logging.js` metadata logging, only after the privacy review in §3.3

---

## 9. Next Steps

Not part of the 18 October submission. Post-submission work.

| Phase | Task | Effort |
|---|---|---|
| 1 | Literature check (wash-trading detection, Sybil-proof accounting) | 1-2 days |
| 2 | Build the market simulation with static attackers | 2-3 days |
| 3 | Part A sweep: find the non-positive-EV region | 1-2 days |
| 4 | Add adaptive tiers A1-A5 with cost accounting | 2-3 days |
| 5 | Train baselines, run grouped and leave-one-attack-out evaluation | 2 days |
| 6 | Write up findings | 2-3 days |
| 7 | Link from the SIMON README | 1 hour |

---

## 10. References to verify before publishing

Citation details below were recalled from memory and must be checked.

- Douceur, "The Sybil Attack" (2002)
- Cheng and Friedman, "Sybilproof Reputation Mechanisms" (2005): global reputation scores cannot be Sybil-proof; flow-based per-observer scores can
- BurstGPT: a real-world LLM serving workload dataset (Azure OpenAI traces)
- Azure LLM inference traces (2023, 2024)
- LMSYS-Chat-1M

---

## 11. Acknowledgements

This proposal emerged from a research discussion on SIMON's wash-compute resistance gap. Thanks to the SIMON maintainers for the honest framing of the problem. The phrase *"Automatic slashing is not enabled, and we say so rather than shipping a threshold we cannot defend"* is what made this approach possible.

---

**Contact:** Yousef Sanjari · [github.com/Josephsjr96](https://github.com/Josephsjr96)
