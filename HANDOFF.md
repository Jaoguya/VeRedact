# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency`, state of 24 October 2026.

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting the
> server, tests there, reruns, prover machines, moving or deleting results). One yes covers one action.

**In short:** on 24 Oct the author replaced the manuscript with `Overleaf/VeRedact-optimize.tex`, which redesigns
Phases 4–6 (CORA, SFMR, SAVER) and the five experiments (ablation variants back, Exp. 5 without gas). The code now
follows it: protocol, variants, the five experiment runners, summaries and figures, all checked test-first and with
local smoke runs. **No experiment has been run with the new code**; every previous result is superseded. Next is a
server check boot, then the full run (section 6).

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
- `Overleaf/VeRedact-optimize.tex` — the final manuscript, never edited here.
- `Other/docs/` — `experiments.md`, `paper-conformance.md` (code vs manuscript), one note per baseline.
- `TASK.md` — log of every task; the last lines list what is open.

Where it runs: one AWS server **veredact-bench** (r7i.4xlarge, 16 vCPU, 128 GB, ~US$1.28/h) with a private Besu
QBFT blockchain on it. Only VeRedact-PQ's Experiment 1 systems use two large spot **prover** machines. Commands go
through `Benchmark/deploy/aws/remote.sh`. The AWS account holds other people's machines: touch only veredact-bench
and the prover/worker machines the experiments create.
Local tests: the laptop has `Benchmark/.venv` (Python 3.12 + Rust STARK module). 7 tests fail there only because
Windows lacks `fork`/`forkserver` (S13, S34, one Exp. 1 test); they run on the server.

## 2. The experiments (VeRedact-optimize.tex)

| Exp. | Question | x-axis | Systems |
|---|---|---|---|
| 0 | Cost of each cryptographic building block | — (table) | all, incl. S99 |
| 1 | Throughput, p95 latency, and execution sharing | rate 100–5,000 req/s; Zipf skew | veredact + 3 variants, S1, S13, S27, S34 |
| 2 | Phase 4 authorization per request and per set | committee 4–32; set size 1–256 | veredact, re-zk, S1, S34, S99 |
| 3 | Audit generation, size, verification, verified nodes | n_Q 10–10^4; records per batch 1, 8, 64 | veredact, shared-evidence, per-record, S1, S13 |
| 4 | Selective PQZK escalation; fault detection | escalation 0–100 %; faults 1–10 % | veredact, S1, S13 |
| 5 | Checkpoint transaction size and finalization latency | affected batches 1–32; validators 4, 7, 10 | veredact |

Scale (author: follow the manuscript): 10^5-transaction ledger, n_Q up to 10^4, 30 repetitions (repetition
tooling `VRPQ_REP` + `scripts/aggregate_reps.py`); Exp. 2–4 also take 30 samples inside each run.

## 3. Status

- Code: done and pushed up to the figures (`git log`); docs updated. Smoke checks on the laptop only.
- Results: none with the new code. Old results (10^6 ledger, previous protocol) are superseded.
- Server stopped, nothing running. October cost so far ~US$225.

## 4. Open problems

1. **Run cost of 30 repetitions.** Exp. 1 alone has 8 systems × (6 rates + 4 skews) points of ~100 s each plus
   setup; 30 repetitions of everything is very expensive. Estimate from logs in the check boot and propose options
   (aws-cost skill) before any run.
2. **Fixed-Batch may out-throughput VeRedact-PQ** at moderate rates (laptop smoke, never a result): CORA's round
   target is λ·T_max, smaller than the fixed 64. If the real run confirms it, the text must explain the
   latency/throughput trade-off (manuscript Exp. 1 discussion already frames it that way).
3. **Manuscript/code gaps** (Other/docs/paper-conformance.md): validation signs twice (rc_i) while the cost table
   says T_S; CORA's f and weights unspecified (code: λ·T_max; w from Exp. 0 costs); Exp. 5 validators [TBD] = 4, 7, 10.
4. **S13's audit times are 3–7 % high** (witnesses timed 8 at a time); bias against S13. Decide re-time or disclose.
5. **Saved histories will be rebuilt** (10^5 ledger and new protocol code): untimed, but costs time on the server.
6. **Housekeeping**: 14 old files from 29 Sep in the server's `Benchmark/results/` root and all old results should
   move to a `_superseded` folder (not deleted) before the new run.

## 5. Decisions needed from the author

- **A. Repetitions.** 30 per point as the manuscript says, or fewer (e.g. 1 run with 30 samples inside, as before)
  — decide after seeing the cost estimate.
- **B. S13 witnesses.** Re-time one at a time (removes the bias, ~8x longer for that step), or state the bias.
- **C. Housekeeping.** Move old results aside on the server (one boot).

## 6. What to do next (each AWS step needs a yes first)

1. Check boot (~30–45 min, ~US$1): pull the branch on the server; `remote.sh '.venv/bin/ruff check src scripts tests
   && .venv/bin/python -m pytest -q'` (all tests incl. S13/S34 and Besu); `make smoke`; move old results aside
   (decision C); estimate run time per experiment from the smoke and old logs.
2. Propose the full-run plan with costs (aws-cost skill), incl. decision A.
3. With a yes: the full run (provers only for VeRedact-PQ's Exp. 1 systems); `scripts/check_coverage.py --tier
   experiment`; `make tables figures`; fetch; one line in `TASK.md`; commit; push.
4. Then the results paragraphs: the author writes the manuscript; text proposals go to a new changes file, the
   .tex is never edited here.

## 7. What to read, in order

1. `TASK.md`, last 20 lines.
2. `Other/docs/experiments.md`.
3. `Overleaf/VeRedact-optimize.tex`, Section Evaluation (what the experiments must show).
4. `Other/docs/aws-runbook.md`.
5. `Other/docs/baselines/*.md`.
6. `Benchmark/deploy/experiments/full_run.sh` (`RESUME=1` finishes a stopped run without provers).
7. `Benchmark/configs/experiments/*.yaml`.
8. `Benchmark/results/logs/` (durations: `=== <exp> done in`, `<exp> <scheme>: N rows in`).

## 8. House rules

- Ask before running anything on AWS; one yes per action.
- No capped results: report a value only if it is a full measurement.
- Never cheat to save cost: no simulated, extrapolated or reused timings; same hardware for every scheme.
- Only this project's AWS resources.
- Never edit `Overleaf/VeRedact-optimize.tex`; mismatches go to `Other/docs/paper-conformance.md`.
- Smoke and pilot numbers are never results.
- Verify a cause before claiming it.
- Lean workspace: extend existing scripts and docs, short comments, one line per task in `TASK.md`.
- Ask before changing outdated docs. Commit or push only when asked.
- Every run gets a hard time limit (`sudo shutdown -h +<minutes>`); the server also powers off 30 min after idle.

## 9. Glossary

- **Redaction**: editing or erasing a transaction already on the chain without breaking it.
- **Chameleon hash**: a hash whose secret-key holder can find a second input with the same hash.
- **Post-quantum**: cryptography meant to resist quantum computers (here ML-DSA-65 and lattice-based hashes).
- **Gas**: the blockchain's unit of on-chain computation and storage cost.
- **Audit, n_Q**: an auditor asks which redactions happened and checks the evidence; n_Q = records returned.
- **Prover**: machine that makes the zero-knowledge proofs VeRedact-PQ's requesters attach.
- **Saturated / overloaded**: requests arrive faster than the scheme finishes them.
- **Lower bound / capped value**: latency counted only until the measurement stopped; the real value is higher.
- **Saved history**: the pre-built ~100,000 redactions audited in Experiments 3–4, saved on the server.
- **Besu**: the Ethereum client running the private test chain.
- **Spot instance**: a cheaper AWS machine that AWS may take back at short notice.
