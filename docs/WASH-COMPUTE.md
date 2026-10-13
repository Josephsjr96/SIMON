# Wash-compute in SIMON

Status: open problem. Nothing in this file is implemented. Date: 2026-10-12.

This file holds the problem statement, the position of the repository, a
research proposal from a team member, and the review of that proposal.
Appendix A holds the proposal in full and unchanged.

## 1. The problem

Wash-compute is self-dealing. A node, or a group of nodes under one owner,
sends jobs to itself. The receipts are valid, and an audit passes, because the
node did the work. The work had no customer.

A receipt proves that a registered node signed an exact answer as the result of
a job. It does not prove that a real user asked for the job. Verification
cannot detect wash-compute. An audit confirms at most that the owner did real
work for itself.

When the client and the executor have the same owner, the payment returns to
that owner. The real cost is electricity plus the fees that leave the owner for
good. If the protocol pays out more than that cost, self-dealing is rational.

One owner can also split into many identities. This is the Sybil attack
(Douceur, 2002) on the demand side. Detection by identity alone therefore
fails.

## 2. Position of this repository

- Emission per unit of work is blocked (`ROADMAP.md`, section "Security gates",
  P0 item 4). Paid and verified work does not prove external demand.
- The whitepaper calls wash-compute unsolvable at the protocol level
  (`docs/whitepaper/SIMON-whitepaper-EN.md`, section 7). The protocol cannot
  know whether the payer and the node are the same party without public
  identity data, and public identity data breaks prompt privacy.
- The ledger can record work. It must not hold a balance of transferable rights
  to future work (`ROADMAP.md`, M5.2).
- Automatic slashing is off. Only provable violations are slashable
  (`docs/EKONOMIA-STAKING.md`).
- The whitepaper proposes a token design: a fixed issuance per epoch, divided
  by share of paid and verified work, plus a non-transferable voucher that a
  user creates by a burn of the token. The whitepaper marks it as a proposal,
  not a decision.

## 3. The proposal

Yousef Sanjari (Joe) wrote "Wash-Compute Resistance: Measure Deterrence and
Detection Together", revision 2, on 2026-10-11. Appendix A holds the full
text. In short:

- Deterrence and detection are complementary. Deterrence fixes the economics.
  A detector is worth only the extra cost that it forces on an attacker who
  wants to evade it.
- Part A is an agent-based simulation of a SIMON-like market. It finds the
  parameters under which self-dealing has a non-positive expected value.
- Part B trains a detector on labeled wash traffic, from five static attacks
  to five adaptive tiers. The headline result is detection recall against
  attacker cost.
- The detector output is a risk score. It feeds re-audit and review. It never
  triggers slashing.
- Honest traffic comes from public LLM serving traces. Privacy rules apply to
  any real logging.

## 4. Review

The SIMON maintainers wrote this review on 2026-10-12. One external critic
read the economic claims (Cursor, model not disclosed). Two further critics
were not available that day.

### 4.1 What the proposal gets right

The framing is correct, and the repository adopts it. Deterrence sets the
economics. Detection is worth only the evasion cost that it imposes. A score
never slashes. The channel list (emission, allocation, build-then-cheat,
metric inflation) is new to this repository, which so far addressed emission
only. The evaluation protocol (grouped splits, leave-one-attack-out, recall at
fixed false-positive rates) is the right one for any detector in SIMON. That
includes the M3 anomaly heuristic.

### 4.2 Gaps

1. The hardest attacker is missing. For an AI farm, wash-compute is
   optimization. The farm routes its own real workload through the network.
   That traffic is real demand from a related party. Evasion costs the farm
   nothing, so detection recall stays at chance. The study must separate two
   cases. Fabricated demand is detectable in principle. Related-party real
   demand is detectable only by economics.

2. The observer is undefined. Most features in section 5.1 of the proposal
   need data that SIMON does not have or plans to hide:
   - Pair concentration, cycle closure, and net inflow need a ledger with
     linkable identities. SIMON has no ledger yet. The privacy plan is one
     pseudonym per counterparty (`ROADMAP.md`, M5.2b). That plan hides these
     features by design.
   - A client has no hardware fingerprint. The executor reports its own
     `exec_profile` and its own timings. Time is an operational signal only,
     never a basis for settlement (`docs/SECURITY-LOG.en.md`, 2026-09-18).
   - Prompt similarity (MinHash) is visible only to the executor, who is the
     attacker here, or to a verifier on the jobs that it samples.

3. The irrecoverable cost is overstated. Verifier fees return to the coalition
   when one of its identities wins the verifier draw. Protocol fees return
   when the protocol pays them out to stakers. A coverage stipend for
   verifiers (`docs/EKONOMIA-STAKING.md`) is a subsidy that the coalition
   collects when it runs verifiers. Only a burn is lost. Even a burn returns
   in part to a coalition that holds the token, because the burn raises the
   value of its holdings.

4. A payoff is missing: prompt access. Jobs go out by a random draw in
   proportion to node power. A node with share s sees about s of all prompts
   (`ROADMAP.md`, section RT3). If wash traffic raises measured power, the
   attacker buys data, not credit. No fee caps that value. The measure of
   power is not decided (D111). The simulation must treat it as a parameter.

5. The score triggers the wrong actions. A re-audit of a wash job finds
   nothing, because the work was real. Re-audit is the right response only to
   the build-then-cheat channel. For wash, the right response is that the job
   earns no credit toward reputation, allocation, or public metrics. A lower
   reputation on suspicion alone breaks the rule "penalize only provable
   violations" (`docs/EKONOMIA-STAKING.md`). To withhold a reward is allowed.
   To take reputation away is not.

6. Part A must test the designs that SIMON considers, not generic parameters:
   - Fee-only, with no emission.
   - Fixed issuance per epoch, divided by work share (the whitepaper proposal).
   - Emission at most equal to the burn (the external audit's remedy).
   - Transferable credits on and off (M5.6).
   - Per-observer, flow-based reputation.
   - Power measured by stake or by calibration jobs, not by job history.

7. The evaluation partly measures itself. Attacker tier A4 and the honest
   users come from the same trace marginals. Hold out real trace segments
   from training. Let a person other than the detector author write the
   attackers.

### 4.3 Corrections about this repository

- There is no demo Worker and no `worker/` directory. The limit of 40 jobs per
  hour is one global counter for the Streamlit demo (`demo/limity.py`).
  Per-job metadata logging exists in the gateway (`SIMON_API_JOBLOG` in
  `tools/simon-api/simon_api.py`). It stores no client identity and no prompt
  text. Deliverable 5 of the proposal is therefore not needed.
- The simulation belongs inside M4.1, the Sybil simulation (D111), and the RT3
  row "wash trading". It needs the same agents and the same identities. A
  separate `sim/` directory duplicates that work.
- Channel 4 (metric inflation) is live today. The `/network` page counts jobs
  and tokens, and all of that traffic comes from the operators. The page must
  say so before judges read it.

## 5. What changes for SIMON

Each item below is a decision for the maintainers, not a done item.

### 5.1 A per-coalition invariant

Take any coalition C of identities. The value that C can extract from a job
must be at most the value that C destroyed for that job and cannot recover.
Fees that C can win back do not count. Only a burn counts, reduced by the share
of the token supply that C holds.

Test every reward flow against this invariant. The external audit's rule
"emission at most equal to net burned fees" is a global cap. It is necessary
but not sufficient, because a global cap does not bound one coalition.

### 5.2 The fixed-pie issuance fails the invariant

Take a fixed issuance P per epoch, divided by share of work, and a burn b per
unit of work. Let W be the total work in the epoch. A wash coalition earns
P/W − b per unit of wash. The profit is positive whenever W < P/b, that is,
whenever the network is under-used. As W grows, the issuance becomes a
one-to-one rebate of the burn, and the profit tends to zero. It never becomes
negative by itself. The early network is the attack window. Helium showed this
pattern.

The whitepaper rejects "emission at most equal to the burn" with the argument
that the farm "gets the work". That is not a gain. The farm runs the same work
locally for the same electricity. The residual holes are elsewhere: unit
pricing (5.3) and allocation (5.4). Mark the fixed-pie proposal in whitepaper
section 7 as rejected. Keep fee-only as the decision.

### 5.3 Unit pricing

The invariant holds only if a unit of work is priced at its true cost in every
class: prefill, decode, and cached prefill (`ROADMAP.md`, M5.3). An attacker
selects the class with the highest reward per unit of real cost. Part A must
include that attacker.

### 5.4 Power is not job history

Measure power for allocation from something that wash cannot inflate. Two
options exist. Bonded stake: an attacker can buy it, but cannot wash it.
Verifier-issued hidden calibration jobs (`docs/design/DESIGN-VERIFIER-0.md`):
they work only if a node cannot tell them from real jobs, and only if the
reserve that pays for them resists Sybil identities. Otherwise they are paid
wash.

### 5.5 Reputation per observer

A global reputation per operator key is the Sybil surface. Cheng and Friedman
(2005) show that per-observer, flow-based scores can be Sybil-proof. In SIMON
each pod ranks nodes on its own paid history. The cost is a cold start for a
new node. A detector score withholds credit. It never subtracts reputation and
never slashes. Add "detector or risk score" to the "Never slashable" list in
`docs/EKONOMIA-STAKING.md`.

### 5.6 THINK by burn only

A voucher earned by work is emission per unit of work under another name. A
user obtains THINK only by a burn. Executors are paid from the fee. Nothing is
minted for a job. Write this into M5.2.

### 5.7 Two problems, two labels

"Unsolvable at the protocol level" is true for related-party real demand.
Fabricated demand is detectable in principle. Payoffs outside the fee ledger
(prompt access, dilution of honest executors) need their own rows in
`docs/THREAT-MODEL.md`.

### 5.8 Where the study lives

Fold the simulation into M4.1. Run Part A over the designs in 5.1 to 5.6
first. Build the detector second, and only after the observer is defined
(per-pod view or verifier-sampled jobs).

### 5.9 Before 18 October

- Label the totals on the `/network` page as operator-generated traffic
  (`ui/src/routes/network/+page.svelte`).
- Add the "Never slashable" line (5.5).
- Add a note in whitepaper section 7 that the fixed-pie proposal fails the
  invariant (5.2).

## 6. References

The references in Appendix A, section 10, are recalled from memory by the
author. Nobody checked them yet. Check them before any publication.

---

## Appendix A. The proposal, unchanged

The text below is by Yousef Sanjari. It is reproduced as written and is not
rewritten to the style rules of this repository.

---

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
