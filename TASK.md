# TASK — full-experiment tracker

Updated 2026-10-03. The manuscript (`overleaf/VeRedact-2.tex`) is final: it is never edited here; text it
needs goes to `overleaf/newchange.md`. Update §1 and the run ledger (§1.1) as each step finishes.

## 1. Progress

Rule: when a step finishes, set **Status** to `done <date>` and write in **Result stored at** the exact path
it produced. `results/` is gitignored: it exists only on the machine that ran it (this laptop or the EC2
instance) and is **not on GitHub**; `paper/` (generated tables + figures) is committed.
`deploy/aws/fetch_results.sh` copies the server's `results/` and `paper/` into this checkout.

**Smoke runs prove nothing.** The smoke tier only checks code paths, stale code and mistakes (does every
experiment and method run, are all files written, does anything crash). Its numbers are never read,
compared or reported; results come only from the experiment tier on the server.

| # | Step | Command | Status | Result stored at |
|:-:|:--|:--|:--|:--|
| 1 | Code aligned with the final manuscript | — | **done** 2026-10-03 | commit `c86a97d` (what changed: §3) |
| 2 | Restructure to the IEEE evaluation-code layout (option B: YAML configs, `src/`, one run per point) | — | **done** 2026-10-03 | commit `f93f640` on GitHub `main` (what changed: §3.2) |
| 3 | Tests + lint | `make test lint` | **done** 2026-10-03 | console only: 44 passed; ruff clean |
| 4 | Local smoke from a fresh `.venv` (laptop, in-process ledger) | `make all TIER=smoke FORCE=--force` | **done** 2026-10-04 (7 min, no errors; after removing variants) | laptop: `results/<exp>/<method>/smoke/` (§1.1); `paper/tables/*.tex`, `paper/figures/*.pdf` (code-path check only; numbers not used) |
| 5 | Start the server | `deploy/aws/provision_ec2.sh` | **done** (existing instance `i-0d832e0ca1fb0c9db` reused; started by `launch_run.sh` 2026-10-04, bootstrap + 46 tests passed on the server) | `deploy/aws/.instance` (gitignored) |
| 6 | Server smoke (Besu + liboqs + STARK build) | `deploy/aws/launch_run.sh smoke` | **done** 2026-10-04 (4 min, no errors, liboqs ML-DSA-65; code-path check only) | server: `results/<exp>/<method>/smoke/`, log `results/logs/smoke_*.log` |
| 7 | Pilot | `deploy/aws/launch_run.sh pilot` | **done** 2026-10-04, fetched; sets D7, D9–D11 | server: `results/<exp>/<method>/pilot/`, log `results/logs/pilot_*.log` |
| 8 | Full experiment | `deploy/aws/launch_run.sh experiment` | **done** 2026-10-05 21:00 ICT (RUN_EXIT=0, server auto-stopped) | server: `results/<exp>/<method>/experiment/`, log `results/logs/experiment_*.log` |
| 9 | Fetch results + paper artifacts | `deploy/aws/fetch_results.sh` | to do | laptop: `results/`, `paper/tables/*.tex`, `paper/figures/*.pdf` |
| 10 | Stop paying | `deploy/aws/teardown_ec2.sh` | to do | — (the idle watchdog powers off after 30 min idle anyway) |
| 11 | Fill the manuscript from the run | `overleaf/newchange.md` §C | to do | `overleaf/newchange.md` |

### 1.1 Run ledger

Every run writes `results/<experiment>/<method>/<tier>/`: `rows.csv` (per request / sample), `metrics.json`,
`config_resolved.yaml`, `run_info.json` (git commit, dirty flag, hardware, library versions, runtime),
`run.log`. A folder with `metrics.json` is finished and is skipped on re-run unless `--force`.
Mapping to the manuscript: `paper/MANIFEST.md`.

| Date | Tier | Machine | Experiments | Location | Status |
|:--|:--|:--|:--|:--|:--|
| 2026-10-04 | smoke | laptop | exp00_primitives | `results/exp00_primitives/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp01_redaction_throughput | `results/exp01_redaction_throughput/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp02_authorization_latency | `results/exp02_authorization_latency/<method>/smoke/` — S1, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp03_audit_efficiency | `results/exp03_audit_efficiency/<method>/smoke/` — S1, S13, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp04_verification_time | `results/exp04_verification_time/<method>/smoke/` — S1, S13, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp05_gas_consumption | `results/exp05_gas_consumption/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only; no gas: in-process ledger) |
| 2026-10-04 | smoke | EC2 | all six | server `results/<exp>/<method>/smoke/` | **current** (code-path check only; not fetched) |
| 2026-10-04 | pilot | EC2 | all six | `results/<exp>/<method>/pilot/` (24 folders, fetched) + `paper/` | **done** 2026-10-04 (attempt 6, ~3.5 h; pilot exp04 n_Q capped at 10^3; attempts 1–4 stopped by harness bugs, fixed: QBFT extraData middleware, nonce reuse across points, executor outliving its point, serial ledger sender capped ~80 tx/s; Exp. 1 pilot results of attempts 1–4 deleted) |
| 2026-10-04 | experiment | EC2 | exp00_primitives | `results/exp00_primitives/<method>/experiment/` | **done** 2026-10-04 (53 s); fetched |
| 2026-10-04 | experiment | EC2 | exp01_redaction_throughput | `results/exp01_redaction_throughput/<method>/experiment/` | **done**: baselines 2026-10-04, VeRedact-PQ re-run 2026-10-05 (15 min; saturated at 100 and 250 req/s, revalidation storm, cause unverified — D7/D12); fetched |
| 2026-10-04 | experiment | EC2 | exp02_authorization_latency | `results/exp02_authorization_latency/<method>/experiment/` | **done** 2026-10-04 (39 min); fetched |
| 2026-10-04 | experiment | EC2 | exp03_audit_efficiency | `results/exp03_audit_efficiency/<method>/experiment/` | **done** 2026-10-05 (61 min; S13 witness reuse, calibration 0.96, 391 witnesses, median 6.9 s each); fetched |
| 2026-10-04 | experiment | EC2 | exp04_verification_time | `results/exp04_verification_time/<method>/experiment/` | **done** 2026-10-05 (~2 h; S13 calibration 0.95); fetched |
| 2026-10-04 | experiment | EC2 | exp05_gas_consumption | `results/exp05_gas_consumption/<method>/experiment/` | **done** 2026-10-05 (20 min); fetched |
| 2026-09-29 – 2026-10-03 | smoke | laptop | old layout | `results/{exp1..exp5,primitives}/<run_id>/`, `results/S*_*.csv` | **deleted** 2026-10-03 (before the restructure; never used for the paper) |

## 2. Decisions still yours (before step 8)

| # | Decision | Now | Recommendation |
|:--|:--|:--|:--|
| D3a | `ledger.validators` | 7 [CONFIRM] | keep 7 (one per organisation); the manuscript's "[TBD]-validator" takes this value |
| D3b | `ledger.netem_delay_ms` | 10 [CONFIRM] | keep 10 unless the paper should model a WAN |
| D3c | `exp01_redaction_throughput.zipf_rate` | **100 [DERIVED]** | see D10 |
| D3d | repetitions | **decided 2026-10-03: one run per point** | manuscript text fix in `newchange.md` D1–D2 |
| D8 | new dependencies `scipy` and `ruff` | **decided 2026-10-03: both added** | scipy 1.18.1 (Mann–Whitney U, t-based CI in `metrics/`); ruff 0.16.10 (`make lint`: check + format, clean on 82 files) |
| D4 | SIS-PQCH distributed perturbation is spherical → statistical leakage of R over many adaptations | open | state as a limitation, or implement the distributed Genise–Micciancio perturbation (cost rises) |
| D6 | SIS n = 256, q = 2^16 not checked with a lattice estimator for NIST level 3 | open | run the estimator before claiming level 3 for PQCH; does not change timings already measured |
| D7 | Exp. 1 load generator | **diagnosed 2026-10-05 (core-isolation test, results/diagnostics/core_isolation.json)**: not the load generator — at 100 req/s requesters submit 99.5 % on time but proofs are 5–8 s old at validation; executor holds the harness write lock 84–87 % of the time at storming points (59–68 % at good ones). Snapshot-read test SKIPPED by author decision: whether the lock overstates the storm is UNVERIFIED — do not call the storm a protocol property | cause vs effect unproven — re-proving load and staleness can feed each other on one shared host; core-isolation test proposed. Data: full run: requesters re-prove every stale request (2.0-2.3 revalidations per request at the storming points); single-core T_ZP = 20.8 ms, so the load generator itself is not the limit. "client-bound" now counts toward the same 2-consecutive-points rule as saturation; `submitted_on_time` reported per point |
| D9 | S1 in Exp. 1: one redaction per block (Jia's rule) | **decided 2026-10-04** | kept as a real limit of S1; text item `overleaf/newchange.md` F1 |
| D10 | Exp. 1 rates and `zipf_rate` | **decided 2026-10-04** | rates = manuscript [100]–[5,000] unchanged; `zipf_rate` = 100 (manuscript: skew sweep "at a fixed arrival rate", its lowest rate); Fig. 3(c) counts every finalized redaction of a point so saturated schemes still have a value |
| D11 | S13 audit cost in Exp. 3–4 | **decided 2026-10-04** | Exp. 4: each S13 response built once per (n_Q, fault fraction), verified samples_per_point times (`AuditQuery.reuse_response`, fidelity-tested); Exp. 3: 5 samples for S13 at n_Q = 10^4 (`samples_override`) |
| D13 | Paper artifacts not in the manuscript | **decided 2026-10-04** | `exp4_granularity` figure and `tab_significance` table deleted (with the Mann–Whitney code); only the manuscript's 5 figures and 2 tables are produced |
| D12 | Exp. 1 early stop vs VeRedact-PQ revalidation storms | **decided 2026-10-04** | full run 2026-10-05: storms are not tied to hot batches — at 100 req/s s=0.0 decided 42 % (14,386 revalidations) while s=0.4-1.2 decided 100 %; any batch touched by an ABRRR round stales every in-flight request on it. stop only after `saturation_patience` = 2 consecutive saturated rates (same rule for every scheme; literally every rate would cost S34 ~8 h of untimed setup); metrics.json reports `decided` and `revalidations` per point. Warm-up point removed (cold start disproven) |
| F1 | Pilot false-positive check (2026-10-04) | **fixed** | (1) block watcher fetched one receipt per tx serially → finality inflated for every scheme above ~80 tx/s: now one `eth_getBlockReceipts` per block; (2) S13 recomputed the accumulated product per audited record: now once per audit (identical witnesses, tested); (3) STARK proofs used all cores and only 4 requester threads: now winterfell built without `concurrent` (each proof single-core on its requester thread; T_ZP single-core) and `client_threads: 16`; (4) idle watchdog never powered off (system python3 cannot import veredact_bench → `set -u` exit): venv python + 30 min fail-safe; (5) reader-preferring RWLock starved the executor under continuous authorizations (S1 at 250 req/s: 4,865 authorized, 0 executed): now writer-preferring, regression-tested; (6) queue_ms < 0 after a resubmission: timings now describe the last attempt. Pilot exp00 + exp01 re-run with these fixes: done 2026-10-04 08:41 UTC, fetched to `results/exp0{0,1}_*/<method>/pilot/`; server stopped |

## 3. What changed (2026-10-03)

### 3.1 Code aligned with the final manuscript

| Area | Change | Why (final manuscript) |
|:--|:--|:--|
| PQZK (Rust AIR + Python) | leaf = Rescue(secret, requester, attribute, expiry); 32-bit range proofs for attribute ≥ policy threshold and expiry > ts_r | Phase 3 Step 4: ValidCred (incl. expiry) ∧ RequesterBound ∧ PrivatePolicy |
| Phase 1 | λ = 256-bit PRF keys; policy/committee records PQ-signed | Phase 1 Steps 2, 6 |
| Phase 2 | data-owner ML-DSA signature over D_i, PBN verification, C_i^orig; Cuckoo filters CF_s; SA-RLI ordered by bucket H_2(τ) mod B | Phase 2 Steps 1, 4 |
| Phase 3 | VPS admission receipt rc_i (one more ML-DSA signature per request) | Phase 3 Step 5 |
| Phase 4 | C_VR rebuilt from the evidence; per-step timings (attestation, freshness, commitment, committee) | Phase 4 Step 2; Exp. 2 decomposition |
| Phase 5 | Auth_e^B and every PBRP_i^auth verified before execution; BIMC multiproof verified before the update | Phase 5 Steps 1, 3 |
| Phase 6 | auditor-signed queries verified by the service; RAI checkpoint binding checked; per-step verification timings | Phase 6 Steps 2, 4; Fig. 6(b) |
| Baseline [1] | "not redacted" proven with an RSA-accumulator non-membership witness per approving node | [1] Sec. III-C3 |
| Baseline [13] | Update checks: old tag, CH collision, new tag | [13] Sec. III-B Redaction/Update |
| Baseline [34] | ChVer by the redactor and by the AVNs | [34] Sec. V-C ChCld step 4 |
| Primitives | new primitive-timing experiment (now `exp00_primitives`) → tab:primitives, VeRedact-PQ and baseline primitives | tab:primitives |
| Figures | panels follow the captions (Fig. 3 throughput/p95/adaptations, Fig. 4 amortized/per-batch, Fig. 6 breakdown, Fig. 7 total/amortized gas) | figure captions |
| Laptop backend | pqcrypto ML-DSA signing retried when its rejection-sampling cap is hit (FIPS 204 loops until success) | sporadic test failure |
| Setup cost | data-owner keys and signatures cached per process (seeded salts) | Exp. 1 re-runs setup per point: saves ≈ 13 h |

Manuscript text the code now differs from: `overleaf/newchange.md` §A (cost-table cells for rc_i and the
Phase 5 Auth check, f in ABRRR, Docker wording) and §B ([TBD]s the code already fixes).

### 3.2 Restructure to the IEEE evaluation-code layout (option B)

| Area | Before | Now |
|:--|:--|:--|
| Configs | `config/{smoke,pilot,experiment}.toml` + `schemes.toml` | `configs/base.yaml`, `datasets/`, `methods/`, `experiments/expNN_*.yaml`, `tiers/` (OmegaConf composition; resolved config saved per run) |
| Code | `benchmark/veredact_bench/`, `experiment/S*/` | `src/veredact_bench/{data,methods,metrics,evaluation,reporting,utils}`; baselines in `methods/baselines/<method>/` |
| Entry points | `python -m veredact_bench run …` | `scripts/run_eval.py`, `make_tables.py`, `make_figures.py`, `validate_config.py`, `capabilities.py`, `paper_reproduction.py` |
| Repetitions | 30 per point | one run per point (author decision); Exp. 2–4 take `samples_per_point` measurements inside it |
| Results | `results/<exp>/<run_id>/{rows.csv,manifest.json}` | `results/<experiment>/<method>/<tier>/{rows.csv,metrics.json,config_resolved.yaml,run_info.json,run.log}`; skip-if-done, `--force` |
| Metrics | inline in plotting | `metrics/` pure functions + tests (percentile, CI, rates, Mann–Whitney U) |
| Paper artifacts | `plot/*.png`, `plot/*.csv` | `paper/figures/*.pdf` (+ .png; IEEE column width, 8 pt, Okabe–Ito colours), `paper/tables/*.tex` (booktabs, best bold), `paper/MANIFEST.md` |
| Logging | `print` | `logging`, one `run.log` per results folder |
| Rust / contracts / tests | `benchmark/pqzk_stark`, `benchmark/contracts`, `benchmark/tests` + `experiment/*/s*_test.py` | `native/pqzk_stark`, `contracts/`, `tests/` (+ `tests/baselines/`) |
| Dependencies | `benchmark/requirements.txt` (unpinned) | root `pyproject.toml`, pinned; `omegaconf`, `scipy`, `ruff` (dev) added (approved) |
| Quality gate | none | `make lint` (ruff check + format, config in `pyproject.toml`) |

## 4. Run time and cost (estimate)

One run per point (2026-10-03), so the experiment tier is much shorter than the earlier 30-repetition estimate:

| Experiment | Points (one run each) | Estimate |
|:--|:--|:--|
| exp00_primitives | 25 operations × 100 samples | minutes |
| exp01_redaction_throughput | 5 schemes × ≤ 10 points × ≈ 100 s (window + drain + setup) | ≈ 1–1.5 h |
| exp02_authorization_latency | 3 × 5 committee sizes × 6 batch sizes × 30 samples | ≈ 0.3 h |
| exp03 + exp04 | 6 histories × n_Q up to 10^4 × 30 samples | ≈ 0.3–0.5 h |
| exp05_gas_consumption | 5 schemes × 1 skew × 6 batch sizes, Besu receipts | ≈ 0.3 h |

c7i.4xlarge in ap-southeast-1 ≈ US$ 0.9/h → ≈ US$ 3–5 for the experiment tier (plus the pilot). The
estimate is replaced by the measured `runtime_s` in each `run_info.json` after the run.

## 5. Docs

`README.md`, `docs/*.md`, `docs/baselines/*.md`, the skill file and `data/README.md` describe the restructured
layout (2026-10-03).


Full run complete 2026-10-05 21:00 ICT: 24 result folders in `results/<exp>/<method>/experiment/`, `paper/figures/` (5 PDFs) and `paper/tables/` (2 .tex) regenerated locally from them; diagnostic `results/diagnostics/core_isolation.json`. Server stopped.

2026-10-05 (late): Exp. 1 throughput redefined as redactions FINALIZED DURING the window / its length (the
arrival-cohort count credited the drain and showed 0 for saturated schemes); metrics.json of all five Exp. 1
results recomputed from the unchanged rows on the server (`scripts/resummarize.py`, old file kept as
`metrics.prev.json`); figures regenerated on the server. All compute now runs on the server
(`deploy/aws/remote.sh`, Makefile forwards on the laptop); skills and plugins removed, only the rtk hook remains.

2026-10-05 (no-cap rule, code only, NOT run yet): author rule "no figure line may end early".
- Exp. 1: early stop removed — every system runs all six rates; saturation is only noted.
- S34: setup (keys + per-record CHash) kept per process and reused across points; integer part in a process pool.
- S1: `txs_per_block` 8 (12,500 blocks); audit histories topped up to max n_Q (`common.fill_history`) — Fig. 5/6
  reach n_Q = 10^4 for S1.
- Exp. 2 / Exp. 5: baselines measured at every batch size m (m independent authorizations / transactions);
  Fig. 4(b) per batch of m0 for every system (`batch_total_ms`).
- To re-run on the server: Exp. 1 (all), Exp. 2 (baselines), Exp. 3–4 (S1), Exp. 5 (baselines). Not started.

- 2026-10-09 — Revised manuscript preview: every overleaf/newchange.md item (A1–A6, B1–B4, D1–D2, E1–E12, F1) applied to a copy, changes in red. Script `scripts/apply_newchange.py`; output `overleaf/revised/VeRedact-2-revised.{tex,pdf}` (compiled on veredact-bench, 21 pages). The original .tex is unchanged.
- 2026-10-10 — **Full run (experiment tier) done**, main @ 6feff77 (manuscript copy `overleaf/revised/VeRedact-2-revised.tex`). Started 2026-10-09 12:43 UTC; prover service crash fixed (5a38d6f) and restarted; S1 Exp. 3 hang (mined transaction never resolved, cause not reproduced) fixed with the anchor safety net (6feff77) and resumed 21:24 UTC; ended 2026-10-10 01:07 UTC: RUN_EXIT=0, coverage 314/314, tables + figures written, server powered off by itself. No anchor recoveries were logged after the restart. Results: `results/<exp>/<method>/experiment/` (24 folders, fetched to the laptop); figures `paper/figures/exp1..exp5_*.{pdf,png}`; tables `paper/tables/tab_primitives.tex`, `tab_gas.tex`. Server logs: `results/logs/full_run_20261009{b,c}.out`.
- 2026-10-10 — Blue manuscript version from the full-run results: `overleaf/revised/VeRedact-2-blue.{tex,pdf}` (22 pages; source of the changed subsection `overleaf/revised/perf_analysis_blue.tex`; figures copied next to it). Only Section V-C Performance Analysis changes; formulas, cost tables and Sections I–IV are identical to `VeRedact-2.tex`. Still [TBD]: gas of policy/committee registration and batch checkpoint (not measured by Exp. 5).
