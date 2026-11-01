# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency` (PR #1), state of 1 November 2026.

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting a machine,
> tests, smoke, reruns, provers, moving or deleting results). One yes covers one action. The full run starts only
> on the exact words **"start full run"**.

**In short:** the code follows the final manuscript `Overleaf/VeRedact-optimize.tex` (accepted as-is: the "Peppo
Implementation Strategy"). **No experiment has run with the current code yet.** The author's limits: on-demand AWS
machines the author controls (nothing local or third-party), budget **US$50**. The plan is the **hybrid plan** (§4),
~US$36–43 for the full run. The code of 1 November is **not tested yet**.

## 1. What the project is

VeRedact-PQ is a **redactable blockchain** scheme (a recorded transaction can later be edited or erased under strict,
auditable rules) built on **post-quantum** cryptography. The paper compares it with earlier schemes (baselines) and
its own ablation variants; this repository measures all of them on the same machine type and data.

| Name in code | Paper ref. | What it is |
|---|---|---|
| `veredact` | this paper | CORA selection + SFMR execution + SAVER audit, post-quantum throughout |
| `veredact-per-request` / `-fixed-batch` / `-cora-no-sfmr` | Exp. 1 variants | no batching / arrival order, size 64 / CORA but one adaptation per request |
| `veredact-re-zk` | Exp. 2 variant | every committee member re-verifies each PQZK proof |
| `veredact-shared-evidence` / `-per-record` | Exp. 3 variants | shared evidence per record / complete evidence per record |
| `S1` / `S13` / `S27` / `S34` | [1] / [13] / [27] / [34] | Improved DCH / EAQ-VRBC / ETCH / REBS, each running its own paper's algorithm |
| `S99` | — | LETA, post-quantum batch authentication; Exp. 0 and 2 only (kept, author 2026-11-01) |

Where things live: `Benchmark/` (code, configs, deploy, tests), `Other/docs/` (experiments, AWS runbook, paper
conformance, one note per baseline), `TASK.md` (open items and log), `AUDIT_LOG.md` (correctness findings).
Results: `Benchmark/results/` on the machines (not in git); `Result/` and `Overleaf/tables/` are written by the run.

## 2. The experiments

| Exp. | Measures | x-axis | Systems | Runs |
|---|---|---|---|---|
| 0 | Cost of each building block (`tab:primitives`) | — | all, incl. S99 | 1 |
| 1 | Throughput, p95 latency (arrival → finalized), execution sharing | rate 100–5,000 req/s; Zipf skew | veredact + 3 variants, S1, S13, S27, S34 | 1 |
| 2 | Phase 4 authorization per request and per set | committee 4–32; set 1–256 | veredact, re-zk, S1, S34, S99 | 3 |
| 3 | Audit generation, size, verification, verified nodes | n_Q 10–10^4; records per batch 1/8/64 | veredact, shared-evidence, per-record, S1, S13 | 3 |
| 4 | Selective PQZK escalation; tampered audit records detected | escalation 0–100 %; faults 1–10 % | veredact, S1, S13 | 3 |
| 5 | Checkpoint size and finalization latency | affected batches 1–32; validators 4/7/10 | veredact | 3 |

Scale: 10^5-transaction ledger, n_Q up to 10^4.

## 3. Why there is a prover machine

- The server **verifies** each PQZK proof (~0.7 ms, timed). **Creating** it (~23 ms median) is the requester's job,
  excluded from server time by the paper (l. 2789).
- At 5,000 req/s that is ~150 cores of proving; on the measured server it slowed VeRedact-PQ 4×. So requesters prove
  on a separate host: one c8g.48xlarge (192 Graviton4 cores, ~7,100 proofs/s estimated from 3,559/s measured on 96).
- Proofs are bound to the request, state and epoch: no precomputing, reuse or fakes. Each prover's first proof must
  verify on the system (`provers._cross_check`), so an ARM/x86 mismatch stops the point instead of hiding as rejections.
- A prover bottleneck can only penalise VeRedact-PQ (its latency includes the wait), never help it.

## 4. The hybrid plan (author 2026-10-31, PR #1)

| Item | Choice |
|---|---|
| Exp. 2–5 | 3 runs × 10 samples per point (30 in total; S13 at n_Q = 10^4: 3 × 2); median = mean of per-run medians with a t CI (2 df); p95 pooled over the runs (`aggregate_reps.py`) |
| Exp. 0, 1 | run 1 only (`config.ONCE`); Exp. 1 throughput CI over 6 × 10-s sub-windows, bootstrap p95 CI; 60 s window + 30 s drain |
| Machines | split run in us-east-2, on demand: one m7i.4xlarge worker per experiment part and run (13: run 1 = e1, e2, e3, e4, e05; runs 2–3 = e2, e3, e4, e05); every system of an experiment on one machine |
| Prover | 1 × c8g.48xlarge (arm64 Ubuntu, full bootstrap), only for run 1's Exp. 1 |
| STARK | f128 field (author) |
| Cost / time | ~US$36–43, ~5–6 h wall time (estimate; Exp. 2–5 hours not yet known) |

Evidence: worst peak memory ever 27.0 GiB (old 10^6 ledger), so 64 GiB is safe; Graviton proof median 22.6 ms =
Intel's, so no prover-hardware bias.

## 5. Decisions and text left to the author

| Item | Choice |
|---|---|
| S13 witness timing | **decided 2026-11-01: re-timed** — each witness timed alone, one after another (~+33 min per Exp. 3/4 worker) |
| S99 | **decided 2026-11-01: kept** in Exp. 0 / 2 (cite it in the manuscript) |
| Manuscript (Overleaf) | repetitions sentence, environment line, prover host sentence, Exp. 1 latency definition, Exp. 5 validators — `Other/docs/paper-conformance.md` §2 |

## 6. Next steps (each AWS step needs the author's yes)

1. Tests + lint on the server: `Benchmark/deploy/aws/remote.sh make test lint`.
2. Commit; rebuild the image: `deploy/aws/build_image.sh` (refuses an uncommitted tree).
3. Smoke: `provision_workers.sh 13`, `TIER=smoke launch_reps.sh 3`, then `TIER=smoke collect_reps.sh 3`. Check: the ARM
   prover boots, the cross-check passes, `submitted_on_time` stays high at 5,000 req/s.
4. On "start full run": `provision_workers.sh 13`, `launch_reps.sh 3`; logs after ~15 min.
5. When all workers are off: `collect_reps.sh 3` (coverage, aggregation, tables, figures), `teardown_workers.sh`.
6. The author writes the results text.

Full commands: `Other/docs/aws-runbook.md`.

## 7. AWS state

| Item | State |
|---|---|
| veredact-bench | r7i.4xlarge, ap-southeast-1; powers itself off when idle |
| us-east-2 | image ami-083cb25ef0de5032b + snap-0de92fbdcccc2a935 (old commit, ~US$5/month; `build_image.sh` replaces it); security groups `veredact-bench`, `veredact-prover`; key pair `veredact-bench` |
| Not ours, never touch | SSO, test-, Apichon-Ubuntu, siemcrypt-eval; in us-east-2 pqbvcd, starfish, des431, snap-0b10404f5d9db0a37, snap-055db4676f7f6676b |

## 8. House rules

- Ask before running anything on AWS; one yes per action; full run only on "start full run".
- No capped results; never simulate, extrapolate or reuse timings; same machine type for every system of an experiment.
- Never edit the manuscript unless the author asks. Smoke numbers are never results. Verify a cause before claiming it.
- Lean workspace, short comments, one line per task in `TASK.md`. Commit/push only when asked.
- Every run has a hard time limit; after any test, check that veredact-bench powered off.

## 9. Glossary

- **Prover**: host that creates VeRedact-PQ requesters' zero-knowledge proofs (load generator, not timed).
- **Verifier**: the server-side pass/reject check of a proof (timed).
- **Part**: the experiments one worker runs (e1 = Exp. 1, e2, e3, e4, e05 = Exp. 0 + 5).
- **Capped value**: a value cut off by a limit; never reported.
- **History**: the redactions audited in Exp. 3–4, built before the timed audits.
