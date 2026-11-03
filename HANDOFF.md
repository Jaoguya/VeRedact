# Handoff — VeRedact-PQ benchmark: full-run results

Branch `fix-launch-guard`, state of 4 November 2026. **The full run is complete** (hybrid plan, finished 3 Nov);
this file tells the next person where the results are and how to check them.

> **Do not run anything on AWS without the author's explicit yes for that specific action.** One yes covers one
> action. Never edit the manuscript (`Overleaf/VeRedact-optimize.tex`) unless the author asks.

## 1. What was run

| Item | Value |
|---|---|
| Manuscript | `Overleaf/VeRedact-optimize.tex` (code accepted as-is: "Peppo Implementation Strategy"; gaps in `Other/docs/paper-conformance.md` §1) |
| Code | commit `ee33357` (`Benchmark/` tree of image `ami-0b477a5fcbfdd36e1`); 109 tests passed |
| Scale | 10^5-transaction ledger, n_Q up to 10^4 |
| Exp. 0, 1 | run 1 only (`config.ONCE`); Exp. 1 error bars from 6 × 10-s sub-windows (throughput) and bootstrap (p95) |
| Exp. 2–5 | 3 runs × 10 samples per point (30 in total; S13 at n_Q = 10^4: 3 × 2); seeds 20260929 + (r−1)·1000 |
| Machines | each experiment part on one AWS m7i.4xlarge (16 vCPU Xeon 8488C, 64 GiB, us-east-2), on demand; VeRedact-PQ's requesters proved on one c8g.48xlarge (192 Graviton4 cores) |
| When | 3 Nov 2026, 02:04–06:14 UTC; run 1's Exp. 3 rerun from 13:10 UTC (see §4) |
| S13 | audit witnesses timed one at a time (author: re-time) |
| S99 | kept in Exp. 0 and 2 (author) |

## 2. Where the results are

| What | Where |
|---|---|
| Figures (paper) | `Result/Pdf/exp1…exp5_*.pdf`, `Result/Picture/exp1…exp5_*.png` (this checkout) |
| Table (paper) | `Overleaf/tables/tab_primitives.tex` |
| Combined results (what the figures and table use) | `Benchmark/results/<exp>/<method>/experiment-reps/metrics.json` |
| Per-run results | `Benchmark/results/<exp>/<method>/experiment-repNN/` (`rows.csv`, `metrics.json`, `config_resolved.yaml`, `run_info.json`, `run.log`) |
| Logs | `Benchmark/results/logs/` (`rep_run_<run>_<part>.out` per worker, `experiment_<exp>_*.log`, `collect_full_20261103c.out`) |
| Copies | `Benchmark/results/` is gitignored (6.6 GB): on this laptop and on veredact-bench (`/opt/veredact/Benchmark/results/`), both complete |

Old runs are in `Benchmark/results/_superseded_*` and the `pilot/`, `scale/`, `smoke-*` folders: never use them.

## 3. How to check the results

| Check | How | Result on 3 Nov |
|---|---|---|
| Every (system, x) point has a value, per run | `VRPQ_REP=r .venv/bin/python scripts/check_coverage.py --tier experiment` (r = 1, 2, 3), on the server via `deploy/aws/remote.sh` | 478/478, 350/350, 350/350 — 0 gaps |
| Runs combined | `scripts/aggregate_reps.py --tier experiment --reps 3` | 28 result sets: Exp. 0/1 copied (run once), Exp. 2–5 three runs |
| Every part finished | `grep -E 'EXIT' Benchmark/results/logs/rep_run_*_e*.out` | all `RUN*_EXIT=0` (run 1 Exp. 3: after the rerun) |
| Regenerate figures and table | `VRPQ_RESULTS_TIER=experiment-reps make tables figures TIER=experiment` (forwarded to the server) | — |
| Same data for every system | `check_coverage.py` compares dataset and history ids per experiment | passed |
| Provenance of a number | `run_info.json` (git commit, hardware, library versions, runtime) and `config_resolved.yaml` next to it | — |

Reading `metrics.json`: keys are `"<axis>=<value>|..."`. In `experiment-reps`, a stats node has `median` (mean of the
per-run medians), `ci95_halfwidth` (Student's t over the 3 runs, 2 df), `p95` (pooled over the runs,
`p95_pooled: true`) and `p95_ci95`. Exp. 1 (`"reps": 1`): `throughput_per_s` with `throughput_per_s_ci95`
(sub-windows), `latency_ms.p95` with `latency_ms.p95_ci95` (bootstrap), `submitted_on_time`, `decided`, censoring flags.

## 4. Things a reader must know

- **Run 1's Exp. 3 was rerun whole** (same seed): the first attempt stopped at 03:05 UTC with "anchoring transaction
  … not mined within 600 s" while reloading the saved history into Besu (`history_cache.load`); cause not
  established. The rerun finished with exit 0; Exp. 3 of runs 2–3 never failed.
- **Prover not a bottleneck:** prover CPU at most ~30 % during Exp. 1 (CloudWatch), so `submitted_on_time` below 1 at
  high rates comes from the system under test, not the requesters' proving.
- **Missed block-watcher receipts:** many `receipt found by hash … (missed by the block watcher)` warnings in Exp. 3;
  each was resolved by the hash lookup (safety net, `anchor.py`); the finished runs left none unresolved.
- **Exp. 1 is one run:** its error bars are within-run (sub-windows, bootstrap), not over runs.
- **Smoke numbers** (`smoke-*` folders) are plumbing checks, never results.

## 5. Left for the author

| Item | Where |
|---|---|
| Results text in Overleaf | from `Result/` and `experiment-reps` |
| Manuscript lines: repetitions, environment (m7i.4xlarge, us-east-2), prover host, Exp. 1 latency definition (arrival → finalized), Exp. 5 validators (4/7/10), S99 citation + Table I row, S13 witness timing disclosure | `Other/docs/paper-conformance.md` §2 |
| Uncommitted: `launch_reps.sh` always re-reads a worker's IP (fix found during the rerun); `TASK.md` lines | commit when asked (it changes `Benchmark/`, so the next launch needs a new image) |
| Merge `fix-launch-guard` into the main line | when asked |

## 6. AWS state (4 Nov) and cost

| Item | State | Cost while idle |
|---|---|---|
| 13 workers `veredact-rep-worker` (us-east-2) | **stopped** (copies only; results are on veredact-bench and here) | disks ~US$2.6/day — terminate when the author says |
| veredact-bench (r7i.4xlarge, ap-southeast-1) | **stopped**, holds all results | disk only |
| Image `ami-0b477a5fcbfdd36e1` / `snap-02f145bfa3aa32fc3` | kept | ~US$5/month |
| Not ours, never touch | SSO, test-, Apichon-Ubuntu, siemcrypt-eval; in us-east-2 pqbvcd, starfish (incl. `starfish-fog-cache` images), des431, snap-0b10404f5d9db0a37, snap-055db4676f7f6676b | — |

Cost: billed US$75 up to 29 Oct; 30 Oct – 3 Nov not yet billed when this was written (estimate ~US$105–115,
including ~US$35 for the failed launch of 1 Nov). Check Cost Explorer for the real totals.

## 7. Where to read more

`TASK.md` (log), `Other/docs/experiments.md` (rules, systems, metrics), `Other/docs/aws-runbook.md` (commands),
`Other/docs/paper-manifest.md` (paper item → script → results folder), `Other/docs/baselines/*.md`, `AUDIT_LOG.md`.

## 8. House rules

- Ask before running anything on AWS; one yes per action. No capped, simulated or reused timings.
- Never edit the manuscript unless the author asks. Smoke numbers are never results. Verify a cause before claiming it.
- Lean workspace, short comments, one line per task in `TASK.md`. Commit/push only when asked.
