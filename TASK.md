# TASK — full-experiment tracker

Updated 2026-11-01. The manuscript is `Overleaf/VeRedact-optimize.tex` (final; edited only by the author; where code
and text differ: `Other/docs/paper-conformance.md`). The plan and how to run it: `HANDOFF.md`. One line per task in
the log below; older history is in git.

## 0. Current state

No experiment has run with the current code; every earlier result is superseded.

| # | Left | Needs |
|:-:|:--|:--|
| 1 | ~~Tests + lint on the server~~ done 2026-11-01: 108 passed, 1 skipped; ruff clean | — |
| 2 | Rebuild the us-east-2 image (`build_image.sh`), smoke of the hybrid plan (`TIER=smoke launch_reps.sh 3`): ARM prover boots, cross-check passes, `submitted_on_time` at 5,000 req/s | author yes each |
| 3 | Full run: `provision_workers.sh 13`, `launch_reps.sh 3`; then `collect_reps.sh 3`, `teardown_workers.sh` | "start full run" |
| 4 | S13 witness timing (up to ~10 % against S13): re-time or disclose | author decision |
| 5 | S99 in Exp. 0 / 2: keep or drop | author decision |
| 6 | Manuscript text (`paper-conformance.md` §2): repetitions, environment, prover host, Exp. 1 latency definition, Exp. 5 validators | author |
| 7 | Results text from the run | after the run |

**Smoke runs prove nothing:** they check code paths only; their numbers are never read or reported.

## Log

- 2026-10-24 — Manuscript switched to `VeRedact-optimize.tex`; protocol (h_st, CORA, Gamma_e, SFMR, SAVER), ablation variants and Exp. 0–5 rebuilt for it; 10^5 ledger, n_Q to 10^4, rates 100–5,000.
- 2026-10-26 — Check boot (server): pytest 101 passed, smoke 0 errors, coverage 123/123. Author: code accepted as-is (Peppo; gaps in `paper-conformance.md` §1).
- 2026-10-28 — Setup profile at 10^5 (server): VeRedact-PQ 32 s/point, S13 28 s, S27 12 s, S34 ~82k targets × 43 ms (~59 min/run).
- 2026-10-28 — Split run by experiment (fair: one machine per comparison): `run_plan.py`, `rep_run.sh`, `launch_reps.sh`, `collect_reps.sh`, prebuilt image (`build_image.sh`).
- 2026-10-30 — Smoke of the split run (us-east-2): 12 parts exit 0. Fixed: prover disk, prover start over ssh, openrsync `***`, per-tier supersede, `test_fidelity` prover leak (veredact-bench up 36.6 h, ~US$47).
- 2026-10-30 — Author: no spot (on demand only); budget US$50.
- 2026-10-31 — Author: STARK field stays f128.
- 2026-10-31 — Checks: worst peak memory 27.0 GiB (old 10^6 ledger), so m7i.4xlarge (64 GiB) is safe. Graviton c8g.24xlarge: proof median 22.6 ms (Intel ~23 ms), 3,559 proofs/s on 96 cores < 5,000, so c8g.48xlarge. ~US$1.
- 2026-10-31 — Author: hybrid plan (Exp. 2–5 × 3 runs of 10 samples, Exp. 0/1 once, m7i.4xlarge workers, one c8g.48xlarge prover, ~US$36–43). PR #1.
- 2026-11-01 — Review fixes (PR #1): ARM prover AMI and AWS CLI by architecture, `[run] worker_type`, environment m7i.4xlarge / us-east-2, prover cross-check (ARM proof verified on x86), `config.ONCE`/`REPS`, pooled p95, Exp. 1 sub-window and bootstrap CIs. Not tested yet.
- 2026-11-01 — Stale removed: one-server and pilot run path (`full_run.sh`, `rep_sequence.sh`, `launch_run.sh`, local provers, pilot/scale tiers, diagnostics), spot code, old figures and table, `Overleaf/newchange.md` and `revised/`, old-manuscript docs and history.
- 2026-11-01 — Server tests: 108 passed, 1 skipped; lint clean after fixing B023 in the Exp. 1 sub-window CI (`summaries.py`).
