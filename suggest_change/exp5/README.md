# Exp. 5 suggested changes

Issue #9. Three parts: **step 1**, the verdict (what Exp. 5 actually measures, and where we lose);
**step 2**, a redesigned experiment (one panel, with baselines, measuring the load the scheme puts on the
chain); **step 3**, one protocol change, needed because on bytes we lose to every baseline.

Everything below is read from release `run-2026-11-03` unpacked into `Benchmark/results/`. Reproduce every
table:

```bash
python Other/analysis/exp5_step1.py
```

**Exp. 5 has no baseline today** (`configs/experiments/exp05_blockchain_overhead.yaml`: `systems: [veredact]`),
so there is no win or loss to report — only a self-characterisation, and two of its three axes turn out to
measure the harness rather than the protocol. That is the finding.

## Step 1 — Why we lose

### The verdict table

| Point / curve | Win/lose (×) | Cause | Kind | Evidence |
|---|---|---|---|---|
| (a) transaction size, ~3.7 KB per affected batch | — (no baseline drawn) | **the ABI model reproduces the measurement exactly**: 334 + 3,712·\|Ω_e\| B signed, where 3,712 = 32 (batch id) + 288 (the 9-word `Checkpoint` struct) + 3,392 (one `bytes` element holding σ_b′: 3,309 B padded to 3,328, plus offset and length words). **σ_b′ alone is 82 % of the transaction at \|Ω_e\| = 1 and 89 % at \|Ω_e\| = 32** | PQ cost | table A (model vs measured: 4,046 / 7,758 / 15,182 / 30,030 / 59,726 / 119,118 against 4,046 … 119,120); `contracts/VeRedactRegistry.sol:9-19,69-84` |
| **(b) latency falls 1.94 s → 1.05 s as \|Ω_e\| grows** | **not a result** | 99.4 % of all 540 samples are **below the 2,000 ms block period**, and within-point std is 36–131 ms. The quantity measured is the wait for the next block, i.e. the block period minus the round's own pre-submission work W. Fitting W over \|Ω_e\| ≥ 4 gives **W = 4.2 ms + 28.4 ms per affected batch** — one SFMR update and one PQCH adaptation per batch. Larger rounds submit later in the block period, so they wait less | unfair harness (the axis measures phase, not consensus) | table B |
| **(b) 4, 7 and 10 validators are indistinguishable** | **not a result** | transaction bytes are **bit-identical** across validator counts (they cannot depend on n), and the latency spread over n is 15–77 ms against a within-point std of 41–405 ms: **spread / std ≤ 0.63** at every \|Ω_e\|. With one host, a 10 ms netem delay and a fixed 2 s block period, QBFT at n ≤ 10 is nowhere near its message-complexity limit | unfair harness (the experiment cannot resolve this axis) | table C |
| **on-chain bytes per finalized redaction vs every baseline** | **lose 2.2–9.5×** (1,757–2,881 B vs 302 B for Scheme [27], 654 B [34], 686 B [13], 814 B [1]) | we write 3.7 KB per *affected batch*, and the measured round composition gives 0.48–0.77 affected batches per redaction (Exp. 1 `batch_batches` / `batch_size`). The baselines write one small `recordRedaction` each | PQ cost (89 % of our bytes are one ML-DSA-65 signature) + workload doesn't use our mechanism (poor SFMR sharing: 0.5–0.8 batches per redaction) | table D1 (baselines: ABI model, a **prediction** until Exp. 5 measures them) and D2 (VeRedact-PQ: exact model at Exp. 1's measured rounds) |
| **anchoring transactions per finalized redaction** | **win 24–69×** (0.0145–0.0411 vs 1.0) | two anchoring transactions per round (`abrrr_authorization`, `redaction_finalization`) over 50–160 finalized redactions; every baseline adapter submits one ledger write per redaction | — | `exp5_layout_preview.py` (Exp. 1 rounds counted in each measurement window); `s01…s34` adapters' single `anchor.submit` per redaction |
| **the \|Ω_e\| axis stops below the operating range** | — | Exp. 5 sweeps \|Ω_e\| ∈ {1, 2, 4, 8, 16, 32}; Exp. 1's rounds touch **32–75 batches on average and up to 117**. The largest point measured is the smallest the system produces | workload doesn't use our mechanism | table E |
| RAI checkpoint, 172 B flat | — | `anchorRai(uint64, bytes32)`: 68 B of calldata plus the ~106 B signed-transaction envelope; independent of \|Ω_e\| and of n, as the figure shows | — | table A; `veredact.py:471` |
| gas is never recorded | — | the Besu anchor resolves every Future to `(ledger_ms, gas_used)` and `_Metered.receipts` keeps it, but Exp. 5 writes neither. Without gas we cannot say whether this chain is transaction-bound or byte/gas-bound — which is exactly what the comparison above turns on | unfair harness (a missing measurement) | `evaluation/anchor.py:43-50`; `exp05_blockchain_overhead.py:71-83` |

Kinds used: *baseline does less · PQ cost · unfair harness · workload doesn't use our mechanism.*

### The two things the current figure cannot say

1. **Fig. 7(b) is a clock, not a consensus measurement.** Every point is one block period minus the round's own
   work. Re-running it with more validators, or more samples, cannot change that.
2. **Without a baseline there is no overhead claim.** "3.6 KB per affected batch" is a number, not a comparison.
   What a reader needs is the on-chain cost of *one redaction* against the schemes that write one transaction
   each — and there we are heavier in bytes and far lighter in transactions.

## Step 2: redesigned Exp. 5

```
What changes:     Exp. 5 becomes a comparison. The systems list gains the four baselines; the measured
                  quantity becomes the load a scheme puts on the PBN per finalized redaction (transactions,
                  with bytes and gas recorded beside it); the |Omega_e| and validator sweeps leave the figure
                  and become a text table and a stated measurement limit.
The one graph:    x = offered load in req/s {100, 250, 500, 1,000, 2,000, 5,000}, log; y = PBN anchoring
                  transactions per finalized redaction, log; five lines: VeRedact-PQ and Schemes [1], [13],
                  [27], [34].
                  Layout preview from measured 3 Nov data: suggest_change/exp5/exp5_layout_preview.png
Expected figure:  measured today - every baseline exactly 1.0 (one ledger write per finalized redaction);
                  VeRedact-PQ 0.0145 (250 req/s) to 0.0411 (2,000 req/s), i.e. 24-69x fewer transactions.
                  The curve is 2 / m: its minimum is at 250 req/s, where CORA's rounds are largest (m = 141).
                  With step 3 nothing in this panel moves - step 3 is about bytes, which the text carries.
Why it's fair:    [x] same hardware for all   - one m7i.4xlarge per run, one 7-validator Besu network,
                      pipelined anchoring for every system (Other/docs/experiments.md 4)
                  [x] baselines per their papers - one ledger write per redaction is each adapter's own
                      design, documented per scheme in Other/docs/baselines/*.md; none is reshaped to batch
                  [x] no point/seed dropped  - all rates, all three runs; the |Omega_e| and validator sweeps
                      stay in the text with their full measured values
                  [x] the case where we don't win is still shown - the text states, with numbers, that we
                      write 2.2-9.5x more BYTES per redaction than every baseline, and why
Text changes:     Fig. 7 caption (one panel, PBN load per redaction); the Exp. 5 paragraph citing (a)/(b)
                  becomes: the exact transaction-size model 334 + 3,712*|Omega_e| B with sigma_b' at 89 % of
                  it; the bytes-per-redaction comparison; one sentence that finalization takes one block
                  period (1.05-1.94 s, every sample under the 2 s period) and that with all validators on one
                  host the 4/7/10 sweep resolves nothing (spread/std <= 0.63) - as a measurement limit, not a
                  result; the RAI checkpoint at 172 B.
Cost:             code ~1 day (systems list, a rate loop, two new row columns: anchoring transactions and
                  tx_bytes per system, plus gas from the receipt the anchor already carries). The panel reuses
                  Exp. 1's workload, so if Exp. 1 is rerun for issue #5 the extra AWS is the Exp. 5 part only.
                  Measured 3 Nov: Exp. 5 is 908 s per run; with the five |Omega_e| points of the text table
                  and the Besu restarts, ~0.4 h per run -> 3 runs ~1.2 h of one m7i.4xlarge (us-east-2,
                  USD 0.806/h) = ~USD 1.0, ~USD 1.5 with the usual 1.5x idle cap. Needs jaoguya's yes.
```

### Numbers moved from the graph to the text

| \|Ω_e\| | 1 | 2 | 4 | 8 | 16 | 32 |
|---|---:|---:|---:|---:|---:|---:|
| finalization transaction (B, measured) | 4,046 | 7,758 | 15,182 | 30,030 | 59,726 | 119,120 |
| per affected batch (B) | 4,046 | 3,879 | 3,796 | 3,754 | 3,733 | 3,723 |
| σ_b′ share | 82 % | 86 % | 88 % | 89 % | 89 % | 89 % |
| finalization latency, n = 7 (s) | 1.91 | 1.91 | 1.89 | 1.74 | 1.55 | 1.08 |

and, per finalized redaction at Exp. 1's measured round composition:

| | VeRedact-PQ | Scheme [1] | Scheme [13] | Scheme [27] | Scheme [34] |
|---|---:|---:|---:|---:|---:|
| anchoring transactions | **0.015–0.041** | 1.0 | 1.0 | 1.0 | 1.0 |
| on-chain bytes | 1,757–2,881 | 814 | 686 | **302** | 654 |

Baseline bytes are the ABI model of `BaselineRedactionLog.recordRedaction` / `recordRedactionWithAcc`
(a prediction; the redesign measures them, as it already measures ours). The `|Ω_e|` axis should run
{1, 8, 32, 64, 128} so that it covers the 32–75 batches per round Exp. 1 actually produces.

## Step 3 — Protocol optimisation

**Step 3 needed: yes** — step 2 shows the transaction-count win, but on bytes per redaction we lose to every
baseline by 2.2–9.5×, and 89 % of our transaction is one signature per affected batch. Status: **proposal**,
not implemented, not measured.

### RoundCheckpoint — one checkpoint signature per round, not one per affected batch

Today Phase 5 produces σ_b′ = Sign(sk_CP, A_b′) for every affected batch and the finalization transaction
carries all \|Ω_e\| of them (`veredact.py:396-406`). But the contract already finalizes the whole round
atomically — `finalizeRedaction` loops over every batch in one transaction and requires one authorization
`bid` for all of them (`VeRedactRegistry.sol:69-84`). The per-batch signature therefore signs a part of
something that is only ever created, anchored and audited as a whole.

```
today     tx = 334 + |Omega_e| * (32 + 288 + 3,392)                    sigma_b' per batch
proposed  tx = 334 + |Omega_e| * (32 + 288 + ceil(log2 |Omega_e|)*32) + 3,392
          one sigma_e = Sign(sk_CP, R_CP) over a Merkle root R_CP of the round's checkpoints,
          plus an inclusion path per batch
```

| | \|Ω_e\| = 32 | at Exp. 1's 1,000 req/s round (\|Ω_e\| = 39, m = 78) |
|---|---:|---:|
| transaction today | 119,120 B | 145,102 B → **1,860 B per redaction** |
| transaction with RoundCheckpoint | **19,086 B** (6.2× smaller) | 23,694 B → **304 B per redaction** |

304 B per redaction is at parity with Scheme [27]'s 302 B and below the other three, while still finalizing
78 redactions in one transaction instead of 78 transactions.

#### Security

- The checkpoint authority's statement changes from "A_b′ is the finalized checkpoint of batch b" to
  "R_CP is the root of this round's finalized checkpoints", plus a Merkle inclusion proof per batch. Collision
  resistance of H gives the per-batch statement back; nothing else in the argument changes.
- Atomicity is unchanged: the round was already all-or-nothing on-chain.
- A verifier that wants one batch's checkpoint now needs ⌈log₂\|Ω_e\|⌉ extra hashes — 5 at \|Ω_e\| = 32,
  0.007 ms at T_H, against the 0.030 ms ML-DSA verification it replaces. **Audit verification gets cheaper,
  not dearer**, which also helps Exp. 3 (`verify_cp_ms`, 14.8 % of audit time).
- Manuscript: Phase 5 Step 5–6 (what is signed and what is anchored), Phase 6 Step 5 (the checkpoint node
  takes a path), Theorem 3 (finalization), Theorem 5 (PBRP contents).

#### Interaction with issue #7

Exp. 3's step 3 O3 proposes anchoring H(A_b′) so the audit *response* need not carry σ_b′. The two changes
compose: with both, σ_b′ disappears from the response **and** from the transaction, and the checkpoint node
costs one hash chain instead of an ML-DSA verification. Propose them together, on whichever issue the reviewer
prefers; they touch the same code (`veredact.py` `_checkpoint` / `execute`, `VeRedactRegistry.sol`) and need
one image rebuild.

### What step 3 does not fix

Finalization still takes one block period, because a permissioned QBFT chain with a 2 s period cannot do
better than that for a transaction submitted mid-period. The honest sentence for the paper is that redaction
finalization costs **one block**, independent of \|Ω_e\| and of the validator count in the range measured —
not that it gets faster with larger rounds.
