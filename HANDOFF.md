# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency`, state of 28 October 2026.

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting the
> server, tests there, reruns, prover machines, moving or deleting results). One yes covers one action.

**In short:** the code follows the final manuscript `Overleaf/VeRedact-optimize.tex` (accepted as-is: the
"Peppo Implementation Strategy", known code/paper gaps are not fixed). Tests (101) and the smoke run pass on the
server. **No experiment has been run with the new code yet.** The run plan was redesigned for cost and time: one run
on three spot workers in ~10 h for ~US$28–33 (instead of ~22 h and ~US$42–46 on one server). It waits for decisions
A–C from the author (section 5) and the exact words **"start full run"**.

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
Besu QBFT blockchain on it. Only VeRedact-PQ's four Experiment 1 systems use two large spot **prover** machines; the
other experiments run on spot **worker** machines of the same type as the server (section 4). Commands go
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

Scale: 10^5-transaction ledger, n_Q up to 10^4, 30 samples per point inside a run. Repetitions: the author decided
**one run first**; 5 runs may follow later (the manuscript now says 5 runs, see decision B).

## 3. Status

| Item | State |
|---|---|
| Code | follows VeRedact-optimize.tex; 101 tests pass on the server; smoke run 0 errors, coverage 123/123 (26 Oct) |
| Results with the new code | **none** |
| Scale run (26 Oct) | stopped in 7 min, nothing measured: `configs/tiers/scale.yaml` had dead n_Q = 10^5 keys; fixed, `validate_config.py scale` 0 errors. The author then chose not to rerun it (option C) |
| Run scripts | single-run and 5-run modes on spot workers, written and syntax-checked, **never run on AWS** |
| Manuscript | author asked: "repeated 30 times" -> "5 independent runs" (lines 3057–3060 and Table params). Not yet synced to Overleaf |
| AWS | everything stopped; no provers, no workers, no open spot requests |
| Uncommitted | single-run mode (`launch_reps.sh`, `rep_exp1_veredact.sh`, `rep_run.sh`, `collect_reps.sh`, `run_experiments.sh`), new `supersede_results.sh`, `TASK.md`, this file |

## 4. Cost and time: what was optimized

Prices are AWS ap-southeast-1 on 27 Oct 2026. Spot = spare AWS capacity at a discount; AWS may take the machine back
at 2 minutes' notice, but the hardware (and so every measured number) is the same as on-demand.

| Machine | On-demand | Spot now |
|---|---|---|
| r7i.4xlarge (server, workers) | US$1.28/h | US$0.54–0.62/h |
| c7i.48xlarge (prover, 192 vCPU) | US$9.88/h | US$3.25–3.57/h (1a, the server's zone, is the dearest) |

**One run, old plan vs new plan**

| | Old: everything on veredact-bench (`full_run.sh`) | New: split run (`launch_reps.sh single`) |
|---|---|---|
| Machines | server ~22 h + 2 provers ~2 h | server ~2 h + 2 provers ~2 h + 3 spot workers ~6–10 h each |
| Wall time | ~22 h | **~10 h** |
| Cost | ~US$42–46 | **~US$28–33** |

What the new plan changes:
1. **Workers on spot** (`provision_workers.sh`): same instance type, ~55 % cheaper. Persistent spot with "stop" on
   interruption: a reclaimed worker keeps its disk; rerunning its part skips finished (experiment, system) folders.
   `teardown_workers.sh` cancels the spot requests first, or AWS would relaunch the workers.
2. **One run split over three workers** (`rep_run.sh <run> a|b|c`): a = Exp. 0, 1 (baselines), 2, 5;
   b = Exp. 3/4 for VeRedact-PQ and S1; c = Exp. 3/4 for S13. Each scheme's Exp. 3/4 history stays on one machine.
3. **The on-demand server only runs VeRedact-PQ's Exp. 1** with the provers (~2 h instead of ~22 h).
4. **Provers serve all four Exp. 1 VeRedact-PQ systems** (before: only `veredact`; the three variants would have run
   without provers and been measured ~4x too slow).
5. **Old results are moved aside at launch** (`supersede_results.sh`): 52 old `experiment/` and `experiment-rep01/`
   folders would otherwise be skipped as "finished" or fill a gap left by a failed worker.
6. **Hard time limits sized to the plan**: server and provers 2.5 h per run (+2 h / +1 h), workers 14 h.

Experiment settings are **unchanged** (same ledger, rates, sweeps, samples, security levels, machine type).

**5 runs** (if chosen later): ~US$125–145 and ~10 h on 15 workers. The single run uses run 1's seed, so it can become
run 1 by renaming its folders; runs 2–5 then cost ~US$100–115.

**Further savings looked at and not taken**

| Option | Saving | Why not |
|---|---|---|
| Provers in the cheapest zone (1c) | ~US$1 per run | the server is in 1a: cross-zone traffic is charged per GB and adds ~1 ms to re-proved requests' latency |
| Server on spot too | ~US$1–2 per run | needs an IAM role on a spot machine; small gain |
| Smaller provers (c7i.24xlarge) | ~US$6–7 per run | may not keep up at 5,000 req/s: VeRedact-PQ points would become client-bound (results change) |
| Fewer samples, shorter Exp. 1 window, fewer sweep points | ~US$1–3 each | results change; must be stated in the paper |
| No provers | ~US$14–18 per run | VeRedact-PQ measured 4x slower (audit A3) |

**Uncertain estimate:** the prover time (~1.5–2 h per run) comes from ~20 min per system measured on the old code.
Each extra prover hour costs ~US$7. If the new code is slower than 2.5 h per run, the server's time limit stops it
and the remaining systems are rerun.

## 5. Decisions needed from the author

| # | Decision | Options | Why it matters |
|---|---|---|---|
| A | **Confirm the [CONFIRM]/[TBD] values** (`configs/base.yaml`) | SIS chameleon hash n = 256, k = 16 (q = 2^16); 7 Besu validators; 10 ms netem delay | they go into the paper's setup text; changing them after the run means rerunning |
| B | **Manuscript repetitions** | keep "5 independent runs" (then run 4 more later) or change back to 1 run | the paper now says 5 runs but only 1 is planned |
| C | **Commit and push** the single-run scripts | yes / no | workers get the code by rsync, but git should match what ran |
| D | **Start** | type exactly **"start full run"** | nothing runs before that |
| E | Later: 5 runs or not | +~US$100–115 | narrower confidence intervals; matches the paper if B keeps 5 runs |

Older open points (unchanged): S13's audit witnesses are timed 8 at a time (3–7 % against S13: re-time or disclose);
bursty on/off workload is in the manuscript but not implemented (config keys only); `scale.yaml` and
`pilot_scale.sh` comments are partly stale.

## 6. What to do next (each AWS step needs the author's yes)

1. Decisions A–C.
2. On "start full run": `deploy/aws/provision_workers.sh 3`, then `deploy/aws/launch_reps.sh single`
   (moves old results aside here and on the server, starts the server's Exp. 1 with provers and the three workers).
3. Check the logs after ~15 min (`results/logs/rep_exp1.out` on the server, `rep_run_r01_<part>.out` on the workers):
   the split scripts have never run on AWS.
4. When all have powered off: `deploy/aws/collect_reps.sh single` (coverage check, tables, figures), then
   `deploy/aws/teardown_workers.sh`. One line in `TASK.md`.
5. The author writes the results text in Overleaf.

## 7. What to read, in order

1. `TASK.md`, last 20 lines.
2. `Other/docs/experiments.md`.
3. `Overleaf/VeRedact-optimize.tex`, Section Evaluation (what the experiments must show).
4. `Other/docs/aws-runbook.md`.
5. `Other/docs/baselines/*.md`.
6. `Benchmark/deploy/aws/launch_reps.sh`, `collect_reps.sh` and `Benchmark/deploy/experiments/rep_run.sh`,
   `rep_exp1_veredact.sh` (the split run); `full_run.sh` is the older one-server run (`RESUME=1` finishes it without provers).
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
