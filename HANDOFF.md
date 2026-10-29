# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency`, state of 28 October 2026 (evening).

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting the
> server, tests there, reruns, prover machines, moving or deleting results). One yes covers one action.

**In short:** the code follows the final manuscript `Overleaf/VeRedact-optimize.tex` (accepted as-is: the
"Peppo Implementation Strategy"). **No experiment has been run with the new code yet.** Final plan (author, 30 Oct):
**three independent runs** in **us-east-2**, **spot machines only** (no spot: nothing starts, nothing on-demand is
paid), split by experiment so each experiment's systems share one machine: two e1 workers (Experiment 1 of runs
1 + 3 and of run 2), each with its own prover pair, and twelve workers for the other experiments. ~8 h,
~US$35–50 (at most ~US$60). Next: rebuild the image, finish the smoke test, then the exact words "start full run".

## 1. What the project is

VeRedact-PQ is a scheme for a **redactable blockchain** (a recorded transaction can later be edited or erased,
e.g. to remove personal data, under strict auditable rules), built on **post-quantum** cryptography. The paper
compares it with earlier schemes (**baselines**) and with its own **ablation variants** (one mechanism switched
off); this repository measures all of them on the same machine and data.

| Name in code | Paper ref. | What it is |
|---|---|---|
| `veredact` | this paper | CORA selection + SFMR execution + SAVER audit, post-quantum throughout |
| `veredact-per-request` / `-fixed-batch` / `-cora-no-sfmr` | Exp. 1 variants | no batching / arrival order, size 64 / CORA but one adaptation per request |
| `veredact-re-zk` | Exp. 2 variant | every committee member re-verifies each PQZK proof |
| `veredact-shared-evidence` / `-per-record` | Exp. 3 variants | shared evidence re-verified per record / complete evidence per record |
| `S1` | [1] | Improved decentralized chameleon hash on Jia's chain (classical) |
| `S13` | [13] | EAQ-VRBC: identity tags + RSA accumulator; compact audit proofs |
| `S27` | [27] | ETCH: lightweight threshold chameleon hash |
| `S34` | [34] | CHET with attribute-based policies |
| `S99` | — | LETA: post-quantum batch authentication; kept in Exp. 0 and 2 by the author although the manuscript dropped it |

Where things live:
- `Benchmark/` — code, configs, deploy scripts, tests; raw results in `Benchmark/results/` (not in git).
- `Result/Pdf`, `Result/Picture` — generated figures (still from the old runs until the new run).
- `Overleaf/VeRedact-optimize.tex` — the final manuscript; edited here only when the author asks.
- `Other/docs/` — `experiments.md`, `paper-conformance.md` (code vs manuscript), one note per baseline.
- `TASK.md` — log of every task; the last lines list what is open.

Where it runs: one AWS server **veredact-bench** (r7i.4xlarge, 16 vCPU, 128 GB, ~US$1.28/h, zone 1a) with a private
Besu QBFT blockchain on it. The full run itself goes to **us-east-2** (`configs/aws.toml` `[run]` region and zone): fourteen spot
**worker** machines of the same type, one per experiment group and run, and two large spot **prover** machines next to the
Experiment 1 worker (section 4). veredact-bench is then only used to collect results and draw tables/figures. Commands go
through `Benchmark/deploy/aws/remote.sh`. The AWS account holds other people's machines: touch only veredact-bench
and the prover/worker machines the experiments create.
Tests, lint, runs and figures run on the server through `remote.sh`, never on the laptop.

## 2. The experiments (VeRedact-optimize.tex)

| Exp. | Question | x-axis | Systems |
|---|---|---|---|
| 0 | Cost of each cryptographic building block | — (table) | all, incl. S99 |
| 1 | Throughput, p95 latency, and execution sharing | rate 100–5,000 req/s; Zipf skew | veredact + 3 variants, S1, S13, S27, S34 |
| 2 | Phase 4 authorization per request and per set | committee 4–32; set size 1–256 | veredact, re-zk, S1, S34, S99 |
| 3 | Audit generation, size, verification, verified nodes | n_Q 10–10^4; records per batch 1, 8, 64 | veredact, shared-evidence, per-record, S1, S13 |
| 4 | Selective PQZK escalation; fault detection | escalation 0–100 %; faults 1–10 % | veredact, S1, S13 |
| 5 | Checkpoint transaction size and finalization latency | affected batches 1–32; validators 4, 7, 10 | veredact |

Scale: 10^5-transaction ledger, n_Q up to 10^4, 30 samples per point within a run, **three runs** (plan C).

## 3. Status

| Item | State |
|---|---|
| Code | follows VeRedact-optimize.tex; 101 tests pass on the server; smoke run 0 errors, coverage 123/123 (26 Oct) |
| Results with the new code | **none** |
| Scale run (26 Oct) | stopped in 7 min, nothing measured: dead n_Q = 10^5 keys in `configs/tiers/scale.yaml`; fixed (`validate_config.py scale` 0 errors); author chose not to rerun it |
| Split-run scripts (us-east-2) | written, syntax-checked, **never run on AWS** |
| Manuscript | 28 Oct (author asked): three independent runs, mean over runs, 95 % CI (t, 2 df); 30 samples per point within a run; not yet synced to Overleaf |
| AWS | everything stopped; nothing in us-east-2 yet (that region also holds other people's key pairs and groups: pqbvcd, starfish, des431 — never touch them) |

## 4. The run plan (C): fair, 3 runs

**Fairness first.** One machine for a whole comparison (`configs/base.yaml` environment), so the run is split by
experiment, never by system. Parts and workers: `Benchmark/src/veredact_bench/utils/run_plan.py` (tested in
`tests/test_run_plan.py`).

| Worker | Part | Runs |
|---|---|---|
| 1 | e1 | Experiment 1 of runs 1 and 3: VeRedact-PQ's four systems with prover pair A, then S1/S13/S27/S34 (~8 h) |
| 2 | e1 | Experiment 1 of run 2, with prover pair B (~4 h) |
| 3–14 | e2, e3, e4, e05 × run 1–3 | Experiment 2; 3; 4 (own history); 0 + 5 |

- Quota (us-east-2, 1,000 spot vCPU): 4 provers × 192 + 14 workers × 16 = 992.
- Spot only: workers one per request across zones; each prover pair tries its e1 worker's zone, then the others,
  and the e1 worker is replaced next to the pair if needed; without spot nothing starts (launched machines are
  terminated).
- Seeds: run r = 20260929 + (r − 1) × 1000; folders `experiment-rep01..03`; `aggregate_reps.py` gives the mean
  over runs and a 95 % CI (Student's t, 2 degrees of freedom) and refuses a missing run.
- Provers: m7i.48xlarge × 2 (same Xeon 8488C and 192 vCPUs as c7i.48xlarge, more memory), then c7i.48xlarge spot,
  then on demand; launched from the laptop into the e1 worker's subnet (us-east-2a); hard limit 2.5 h per run + 1 h;
  stop themselves 15 min after use. `provision_provers.sh` now fails (and terminates them) unless every prover
  listens; before 28 Oct it never started the service from macOS (`timeout` missing).
- Prebuilt image (`build_image.sh`): workers and provers start in ~3 min instead of ~25; deleted by
  `teardown_workers.sh`.
- Real values only: tables never take published numbers; every request is kept; a point stopped by a time limit
  is a coverage gap; a failed part is rerun whole for its run (`FORCE=--force`); the Experiment 3/4 history is
  real redactions built before the timed audits. One fixed input: CORA's weights (21 Oct Experiment 0).

**Measured setup (28 Oct, server, 10^5 ledger; untimed, per Experiment 1 point):** VeRedact-PQ 32 s, S13 28 s,
S27 12 s, S1 reused after its first point, S34 43 ms per newly targeted record (~82,000 per run, ~59 min).
Reusing/parallelizing setup was dropped: ~40 min per run saved, not worth changing four schemes.

**Cost and time (estimates, spot prices of 28–30 Oct):** provers ~12 prover-hours (~US$24–37), 14 workers
(~US$0.26/h, ~US$9–13), image and collecting ~US$2: **~US$35–50, ~8 h** (e1 worker 1 is the longest part).
Smoke of 30 Oct: no spot at all in us-east-2 at that moment (everything fell back to on-demand, ~US$14); the
fallback is now removed.
Earlier timings from 19–21 Oct were at the old 10^6 ledger and are ~10× too long for setup.

## 5. Decisions needed from the author

All plan questions are settled (28 Oct grilling). Left: say **"start full run"** after the smoke test. Older open
points: S13's audit witnesses timed 8 at a time (3–7 % against S13: re-time or disclose); bursty workload not
implemented; the paper does not name the prover machines yet.

## 6. What to do next (each AWS step needs the author's yes)

1. Commit (and push when asked); the image is built from the committed tree.
2. Smoke test of plan C (~US$3–5): `deploy/aws/build_image.sh` (refuses an uncommitted tree);
   `deploy/aws/provision_workers.sh 14`; `TIER=smoke deploy/aws/launch_reps.sh 3`; when the workers are off,
   `TIER=smoke deploy/aws/collect_reps.sh 3` (coverage + aggregation on veredact-bench, nothing moved aside);
   `TIER=smoke deploy/aws/teardown_workers.sh` (keeps the image for the full run).
   A failed part: `ONLY="<worker n>" FORCE=--force deploy/aws/launch_reps.sh 3` reruns it whole.
3. On "start full run": `provision_workers.sh 14` then at once `launch_reps.sh 3`; check logs after ~15 min.
4. When all have powered off: `collect_reps.sh 3` (aggregate, tables, figures), `teardown_workers.sh`.
5. The author writes the results text in Overleaf.

## 7. What to read, in order

1. `TASK.md`, last 20 lines.
2. `Other/docs/experiments.md`.
3. `Overleaf/VeRedact-optimize.tex`, Section Evaluation (what the experiments must show).
4. `Other/docs/aws-runbook.md`.
5. `Other/docs/baselines/*.md`.
6. `Benchmark/deploy/experiments/rep_run.sh`, `Benchmark/deploy/aws/launch_reps.sh`, `collect_reps.sh` (the split
   run); `full_run.sh` is the older one-server run (`RESUME=1` finishes it without provers).
7. `Benchmark/configs/experiments/*.yaml`.
8. `Benchmark/results/logs/` (durations: `=== <exp> done in`, `<exp> <scheme>: N rows in`).

## 8. House rules

- Ask before running anything on AWS; one yes per action. The full run starts only on "start full run".
- No capped results: report a value only if it is a full measurement.
- Never cheat to save cost: no simulated, extrapolated or reused timings; same hardware for every scheme.
- Only this project's AWS resources.
- Never edit `Overleaf/VeRedact-optimize.tex` unless the author asks; mismatches go to `Other/docs/paper-conformance.md`.
- Smoke and pilot numbers are never results.
- Verify a cause before claiming it.
- Lean workspace: extend existing scripts and docs, short comments, one line per task in `TASK.md`.
- Ask before changing outdated docs. Commit or push only when asked.
- Every run gets a hard time limit (`sudo shutdown -h +<minutes>`); the server also powers off 30 min after idle.

## 9. Glossary

- **Redaction**: editing or erasing a transaction already on the chain without breaking it.
- **Chameleon hash**: a hash whose secret-key holder can find a second input with the same hash.
- **Post-quantum**: cryptography meant to resist quantum computers (here ML-DSA-65 and lattice-based hashes).
- **Audit, n_Q**: an auditor asks which redactions happened and checks the evidence; n_Q = records returned.
- **Prover**: machine that makes the zero-knowledge proofs VeRedact-PQ's requesters attach.
- **Saturated / overloaded**: requests arrive faster than the scheme finishes them.
- **Lower bound / capped value**: latency counted only until the measurement stopped; the real value is higher.
- **History**: the redactions audited in Experiments 3–4, built before the timed audits (not timed; `evaluation/history_cache.py`).
- **Besu**: the Ethereum client running the private test chain.
- **Spot instance**: a cheaper AWS machine that AWS may take back at short notice.
