# TASK — full-experiment tracker

Updated 2026-10-24. The manuscript is `Overleaf/VeRedact-optimize.tex` (final, never edited here; mismatches go to
`Other/docs/paper-conformance.md`). §0 is the current state; §1–§5 are the history of the previous manuscript
(VeRedact-2.tex) and its runs, kept for the record. The dated log at the end lists every task.

## 0. Current state (2026-10-24)

The code follows VeRedact-optimize.tex. No experiment has run with it yet; every earlier result is superseded.

### 0.1 Done

| Area | What | Commit |
|:--|:--|:--|
| Manuscript | VeRedact-optimize.tex replaces VeRedact-2.tex and the revised/blue copies | `f378786` |
| Phase 3 | state digest h_i^st from batch b's checkpoint; state-bound statement, C_VR and freshness | `8156ca0` |
| Phase 4 | CORA selector (`protocol/cora.py`); plan commitment Gamma_e; C_e^B signed directly | `252f735`, `ac1dfdc` |
| Phase 5 | SFMR frontier, Theta_b, Xi_b, P_exec in P_auth (execution outside the plan withheld) | `ac1dfdc` |
| Phase 6 | SAVER: evidence nodes, verified-context store, per-request PQZK escalation, checkpoint signature now verified | `10c2811` |
| Variants | `veredact-<variant>`: per-request, fixed-batch, cora-no-sfmr, re-zk, shared-evidence, per-record | `a8f182c` |
| Exp. 1 | CORA rounds in the executor; rates 100–5,000; |Omega_e|, adaptations, F_e per 1,000; Fig. 3(c) | `2d723d8` |
| Exp. 2 | Phase 4 per request and per set; Re-ZK; LETA kept | `7308145` |
| Exp. 3 / 4 | SAVER efficiency with sharing axis 1/8/64 and verified nodes; escalation 0–100 % and fault classes | `b011327` |
| Exp. 5 | `exp05_blockchain_overhead`: tx size + finality vs |Omega_e| 1–32, validators 4/7/10; gas removed | `bc2d594` |
| Figures | Fig. 3–7 follow the new captions; result loader keeps variant keys | `5ea1a26` |
| Docs | HANDOFF, README, experiments, manifest, conformance | `a2efefc` |
| Tests | `tests/test_protocol.py` at four seams + variants; laptop env `Benchmark/.venv` (93 pass; 7 need Linux fork) | — |

### 0.2 Left

| # | Step | Needs |
|:-:|:--|:--|
| 1 | Check boot: pull branch, full tests (incl. S13, S34, Besu), `make smoke`, move old results aside, time estimate | author yes (~30–45 min, ~US$1) |
| 2 | Full-run plan with cost options (aws-cost skill); decide repetitions (manuscript: 30) | author decision |
| 3 | Full run (provers only for VeRedact-PQ's Exp. 1 systems), coverage check, tables + figures, fetch | author yes |
| 4 | Results text for the author; watch Fixed-Batch vs CORA throughput (laptop smoke hint) | after the run |
| 5 | S13 witness timing 3–7 % high: re-time or disclose | author decision |
| 6 | Manuscript gaps to resolve in the text: validation 2·T_S (rc_i), CORA f and weights, Exp. 5 validators | author |


## 1. Progress (history: VeRedact-2.tex runs, superseded 2026-10-24)

Rule: when a step finishes, set **Status** to `done <date>` and write in **Result stored at** the exact path
it produced. `Benchmark/results/` is gitignored: it exists only on the machine that ran it (this laptop or the EC2
instance) and is **not on GitHub**; `Result/` (generated tables + figures) is committed.
`Benchmark/deploy/aws/fetch_results.sh` copies the server's `Benchmark/results/` and `Result/` into this checkout.

**Smoke runs prove nothing.** The smoke tier only checks code paths, stale code and mistakes (does every
experiment and method run, are all files written, does anything crash). Its numbers are never read,
compared or reported; results come only from the experiment tier on the server.

| # | Step | Command | Status | Result stored at |
|:-:|:--|:--|:--|:--|
| 1 | Code aligned with the final manuscript | — | **done** 2026-10-03 | commit `c86a97d` (what changed: §3) |
| 2 | Restructure to the IEEE evaluation-code layout (option B: YAML configs, `Benchmark/src/`, one run per point) | — | **done** 2026-10-03 | commit `f93f640` on GitHub `main` (what changed: §3.2) |
| 3 | Tests + lint | `make test lint` | **done** 2026-10-03 | console only: 44 passed; ruff clean |
| 4 | Local smoke from a fresh `.venv` (laptop, in-process ledger) | `make all TIER=smoke FORCE=--force` | **done** 2026-10-04 (7 min, no errors; after removing variants) | laptop: `Benchmark/results/<exp>/<method>/smoke/` (§1.1); `Overleaf/tables/*.tex`, `Result/Pdf/*.pdf` (code-path check only; numbers not used) |
| 5 | Start the server | `Benchmark/deploy/aws/provision_ec2.sh` | **done** (existing instance `i-0d832e0ca1fb0c9db` reused; started by `launch_run.sh` 2026-10-04, bootstrap + 46 tests passed on the server) | `Benchmark/deploy/aws/.instance` (gitignored) |
| 6 | Server smoke (Besu + liboqs + STARK build) | `Benchmark/deploy/aws/launch_run.sh smoke` | **done** 2026-10-04 (4 min, no errors, liboqs ML-DSA-65; code-path check only) | server: `Benchmark/results/<exp>/<method>/smoke/`, log `Benchmark/results/logs/smoke_*.log` |
| 7 | Pilot | `Benchmark/deploy/aws/launch_run.sh pilot` | **done** 2026-10-04, fetched; sets D7, D9–D11 | server: `Benchmark/results/<exp>/<method>/pilot/`, log `Benchmark/results/logs/pilot_*.log` |
| 8 | Full experiment | `Benchmark/deploy/aws/launch_run.sh experiment` | **done** 2026-10-05 21:00 ICT (RUN_EXIT=0, server auto-stopped) | server: `Benchmark/results/<exp>/<method>/experiment/`, log `Benchmark/results/logs/experiment_*.log` |
| 9 | Fetch results + paper artifacts | `Benchmark/deploy/aws/fetch_results.sh` | to do | laptop: `Benchmark/results/`, `Overleaf/tables/*.tex`, `Result/Pdf/*.pdf` |
| 10 | Stop paying | `Benchmark/deploy/aws/teardown_ec2.sh` | to do | — (the idle watchdog powers off after 30 min idle anyway) |
| 11 | Fill the manuscript from the run | `Overleaf/newchange.md` §C | to do | `Overleaf/newchange.md` |

### 1.1 Run ledger

Every run writes `Benchmark/results/<experiment>/<method>/<tier>/`: `rows.csv` (per request / sample), `metrics.json`,
`config_resolved.yaml`, `run_info.json` (git commit, dirty flag, hardware, library versions, runtime),
`run.log`. A folder with `metrics.json` is finished and is skipped on re-run unless `--force`.
Mapping to the manuscript: `Other/docs/paper-manifest.md`.

| Date | Tier | Machine | Experiments | Location | Status |
|:--|:--|:--|:--|:--|:--|
| 2026-10-04 | smoke | laptop | exp00_primitives | `Benchmark/results/exp00_primitives/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp01_redaction_throughput | `Benchmark/results/exp01_redaction_throughput/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp02_authorization_latency | `Benchmark/results/exp02_authorization_latency/<method>/smoke/` — S1, S34, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp03_audit_efficiency | `Benchmark/results/exp03_audit_efficiency/<method>/smoke/` — S1, S13, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp04_verification_time | `Benchmark/results/exp04_verification_time/<method>/smoke/` — S1, S13, veredact | **current** (code-path check only) |
| 2026-10-04 | smoke | laptop | exp05_gas_consumption | `Benchmark/results/exp05_gas_consumption/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (code-path check only; no gas: in-process ledger) |
| 2026-10-04 | smoke | EC2 | all six | server `Benchmark/results/<exp>/<method>/smoke/` | **current** (code-path check only; not fetched) |
| 2026-10-04 | pilot | EC2 | all six | `Benchmark/results/<exp>/<method>/pilot/` (24 folders, fetched) + `Result/` | **done** 2026-10-04 (attempt 6, ~3.5 h; pilot exp04 n_Q capped at 10^3; attempts 1–4 stopped by harness bugs, fixed: QBFT extraData middleware, nonce reuse across points, executor outliving its point, serial ledger sender capped ~80 tx/s; Exp. 1 pilot results of attempts 1–4 deleted) |
| 2026-10-04 | experiment | EC2 | exp00_primitives | `Benchmark/results/exp00_primitives/<method>/experiment/` | **done** 2026-10-04 (53 s); fetched |
| 2026-10-04 | experiment | EC2 | exp01_redaction_throughput | `Benchmark/results/exp01_redaction_throughput/<method>/experiment/` | **done**: baselines 2026-10-04, VeRedact-PQ re-run 2026-10-05 (15 min; saturated at 100 and 250 req/s, revalidation storm, cause unverified — D7/D12); fetched |
| 2026-10-04 | experiment | EC2 | exp02_authorization_latency | `Benchmark/results/exp02_authorization_latency/<method>/experiment/` | **done** 2026-10-04 (39 min); fetched |
| 2026-10-04 | experiment | EC2 | exp03_audit_efficiency | `Benchmark/results/exp03_audit_efficiency/<method>/experiment/` | **done** 2026-10-05 (61 min; S13 witness reuse, calibration 0.96, 391 witnesses, median 6.9 s each); fetched |
| 2026-10-04 | experiment | EC2 | exp04_verification_time | `Benchmark/results/exp04_verification_time/<method>/experiment/` | **done** 2026-10-05 (~2 h; S13 calibration 0.95); fetched |
| 2026-10-04 | experiment | EC2 | exp05_gas_consumption | `Benchmark/results/exp05_gas_consumption/<method>/experiment/` | **done** 2026-10-05 (20 min); fetched |
| 2026-09-29 – 2026-10-03 | smoke | laptop | old layout | `Benchmark/results/{exp1..exp5,primitives}/<run_id>/`, `Benchmark/results/S*_*.csv` | **deleted** 2026-10-03 (before the restructure; never used for the paper) |

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
| D7 | Exp. 1 load generator | **diagnosed 2026-10-05 (core-isolation test, Benchmark/results/diagnostics/core_isolation.json)**: not the load generator — at 100 req/s requesters submit 99.5 % on time but proofs are 5–8 s old at validation; executor holds the harness write lock 84–87 % of the time at storming points (59–68 % at good ones). Snapshot-read test SKIPPED by author decision: whether the lock overstates the storm is UNVERIFIED — do not call the storm a protocol property | cause vs effect unproven — re-proving load and staleness can feed each other on one shared host; core-isolation test proposed. Data: full run: requesters re-prove every stale request (2.0-2.3 revalidations per request at the storming points); single-core T_ZP = 20.8 ms, so the load generator itself is not the limit. "client-bound" now counts toward the same 2-consecutive-points rule as saturation; `submitted_on_time` reported per point |
| D9 | S1 in Exp. 1: one redaction per block (Jia's rule) | **decided 2026-10-04** | kept as a real limit of S1; text item `Overleaf/newchange.md` F1 |
| D10 | Exp. 1 rates and `zipf_rate` | **decided 2026-10-04** (rates superseded 2026-10-23: 1–1,000 req/s) | rates = manuscript [100]–[5,000] unchanged; `zipf_rate` = 100 (manuscript: skew sweep "at a fixed arrival rate", its lowest rate); Fig. 3(c) counts every finalized redaction of a point so saturated schemes still have a value |
| D11 | S13 audit cost in Exp. 3–4 | **decided 2026-10-04** | Exp. 4: each S13 response built once per (n_Q, fault fraction), verified samples_per_point times (`AuditQuery.reuse_response`, fidelity-tested); Exp. 3: 5 samples for S13 at n_Q = 10^4 (`samples_override`) |
| D13 | Paper artifacts not in the manuscript | **decided 2026-10-04** | `exp4_granularity` figure and `tab_significance` table deleted (with the Mann–Whitney code); only the manuscript's 5 figures and 2 tables are produced |
| D12 | Exp. 1 early stop vs VeRedact-PQ revalidation storms | **decided 2026-10-04** | full run 2026-10-05: storms are not tied to hot batches — at 100 req/s s=0.0 decided 42 % (14,386 revalidations) while s=0.4-1.2 decided 100 %; any batch touched by an ABRRR round stales every in-flight request on it. stop only after `saturation_patience` = 2 consecutive saturated rates (same rule for every scheme; literally every rate would cost S34 ~8 h of untimed setup); metrics.json reports `decided` and `revalidations` per point. Warm-up point removed (cold start disproven) |
| F1 | Pilot false-positive check (2026-10-04) | **fixed** | (1) block watcher fetched one receipt per tx serially → finality inflated for every scheme above ~80 tx/s: now one `eth_getBlockReceipts` per block; (2) S13 recomputed the accumulated product per audited record: now once per audit (identical witnesses, tested); (3) STARK proofs used all cores and only 4 requester threads: now winterfell built without `concurrent` (each proof single-core on its requester thread; T_ZP single-core) and `client_threads: 16`; (4) idle watchdog never powered off (system python3 cannot import veredact_bench → `set -u` exit): venv python + 30 min fail-safe; (5) reader-preferring RWLock starved the executor under continuous authorizations (S1 at 250 req/s: 4,865 authorized, 0 executed): now writer-preferring, regression-tested; (6) queue_ms < 0 after a resubmission: timings now describe the last attempt. Pilot exp00 + exp01 re-run with these fixes: done 2026-10-04 08:41 UTC, fetched to `Benchmark/results/exp0{0,1}_*/<method>/pilot/`; server stopped |

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

Manuscript text the code now differs from: `Overleaf/newchange.md` §A (cost-table cells for rc_i and the
Phase 5 Auth check, f in ABRRR, Docker wording) and §B ([TBD]s the code already fixes).

### 3.2 Restructure to the IEEE evaluation-code layout (option B)

| Area | Before | Now |
|:--|:--|:--|
| Configs | `config/{smoke,pilot,experiment}.toml` + `schemes.toml` | `Benchmark/configs/base.yaml`, `datasets/`, `methods/`, `experiments/expNN_*.yaml`, `tiers/` (OmegaConf composition; resolved config saved per run) |
| Code | `benchmark/veredact_bench/`, `experiment/S*/` | `Benchmark/src/veredact_bench/{data,methods,metrics,evaluation,reporting,utils}`; baselines in `methods/baselines/<method>/` |
| Entry points | `python -m veredact_bench run …` | `Benchmark/scripts/run_eval.py`, `make_tables.py`, `make_figures.py`, `validate_config.py`, `capabilities.py`, `paper_reproduction.py` |
| Repetitions | 30 per point | one run per point (author decision); Exp. 2–4 take `samples_per_point` measurements inside it |
| Results | `Benchmark/results/<exp>/<run_id>/{rows.csv,manifest.json}` | `Benchmark/results/<experiment>/<method>/<tier>/{rows.csv,metrics.json,config_resolved.yaml,run_info.json,run.log}`; skip-if-done, `--force` |
| Metrics | inline in plotting | `metrics/` pure functions + tests (percentile, CI, rates, Mann–Whitney U) |
| Paper artifacts | `plot/*.png`, `plot/*.csv` | `Result/Pdf/*.pdf` (+ .png; IEEE column width, 8 pt, Okabe–Ito colours), `Overleaf/tables/*.tex` (booktabs, best bold), `Other/docs/paper-manifest.md` |
| Logging | `print` | `logging`, one `run.log` per results folder |
| Rust / contracts / tests | `benchmark/pqzk_stark`, `benchmark/contracts`, `benchmark/tests` + `experiment/*/s*_test.py` | `Benchmark/native/pqzk_stark`, `Benchmark/contracts/`, `Benchmark/tests/` (+ `Benchmark/tests/baselines/`) |
| Dependencies | `benchmark/requirements.txt` (unpinned) | root `Benchmark/pyproject.toml`, pinned; `omegaconf`, `scipy`, `ruff` (dev) added (approved) |
| Quality gate | none | `make lint` (ruff check + format, config in `Benchmark/pyproject.toml`) |

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

`README.md`, `Other/docs/*.md`, `Other/docs/baselines/*.md`, the skill file and `Other/data/README.md` describe the restructured
layout (2026-10-03).


Full run complete 2026-10-05 21:00 ICT: 24 result folders in `Benchmark/results/<exp>/<method>/experiment/`, `Result/` (5 PDFs) and `Overleaf/tables/` (2 .tex) regenerated locally from them; diagnostic `Benchmark/results/diagnostics/core_isolation.json`. Server stopped.

2026-10-05 (late): Exp. 1 throughput redefined as redactions FINALIZED DURING the window / its length (the
arrival-cohort count credited the drain and showed 0 for saturated schemes); metrics.json of all five Exp. 1
results recomputed from the unchanged rows on the server (`Benchmark/scripts/resummarize.py`, old file kept as
`metrics.prev.json`); figures regenerated on the server. All compute now runs on the server
(`Benchmark/deploy/aws/remote.sh`, Makefile forwards on the laptop); skills and plugins removed, only the rtk hook remains.

2026-10-05 (no-cap rule, code only, NOT run yet): author rule "no figure line may end early".
- Exp. 1: early stop removed — every system runs all six rates; saturation is only noted.
- S34: setup (keys + per-record CHash) kept per process and reused across points; integer part in a process pool.
- S1: `txs_per_block` 8 (12,500 blocks); audit histories topped up to max n_Q (`common.fill_history`) — Fig. 5/6
  reach n_Q = 10^4 for S1.
- Exp. 2 / Exp. 5: baselines measured at every batch size m (m independent authorizations / transactions);
  Fig. 4(b) per batch of m0 for every system (`batch_total_ms`).
- To re-run on the server: Exp. 1 (all), Exp. 2 (baselines), Exp. 3–4 (S1), Exp. 5 (baselines). Not started.

- 2026-10-09 — Revised manuscript preview (newchange.md applied, red): `Overleaf/revised/VeRedact-2-revised.{tex,pdf}` via `Benchmark/scripts/apply_newchange.py`.
- 2026-10-10 — Full run done (coverage 314/314): `Benchmark/results/<exp>/<method>/experiment/`, `Result/`, `Overleaf/tables/`; logs `full_run_20261009{b,c}.out`. Superseded.
- 2026-10-10 — Blue manuscript: `Overleaf/revised/VeRedact-2-blue.{tex,pdf}` (Section V-C only; extract `perf_analysis_blue.tex`).
- 2026-10-11 — Repository re-laid out: `Overleaf/`, `Result/{Pdf,Picture}`, `Benchmark/`, `Reference/`, `Other/`; server at `/opt/veredact/Benchmark`. Older entries use old paths.
- 2026-10-15 — Reference S99 (LETA): `Reference/S99_Li2026_LETA/`.
- 2026-10-16 — S99 added as post-quantum baseline (Exp. 0, Exp. 2): `methods/baselines/s99_leta/`, `Other/docs/baselines/S99-leta.md`. Exp. 1 latency made end-to-end with censoring at the cutoff.
- 2026-10-16 — Full run (Exp. 1 all, S99) done, coverage 374/374; logs `full_run_20261016b.out`. Superseded.
- 2026-10-17 — Blue manuscript: LETA [39], Exp. 1/2 text; Fig. 3/4/6/7 reworked; Exp. 2 = complete authorization.
- 2026-10-17 — Repetition tooling (`VRPQ_REP`, `aggregate_reps.py`, `rep_*.sh`, `check_rep.py`); reps 1-2 run (`experiment-rep01/02`). Revoked 2026-10-19; tooling kept as optional.
- 2026-10-18 — Scale-up (author): 10^6-transaction ledger, n_Q up to 10^5, S1 1-transaction blocks (disclosed); veredact-bench c7i.4xlarge -> r7i.4xlarge after pilot out-of-memory.
- 2026-10-18 — Prover start-up bias fixed (workers pre-started, clock after handshake); provers on spot first.
- 2026-10-19 — One run (repetitions revoked); one history list for every scheme (`data/history.py`); saved histories (`evaluation/history_cache.py`); auditors read the chain (VeRedact-PQ CP_e^A + MR_b', S1 accumulator + records; S13 trusted node). Memory probe OK (`scripts/memory_probe.py`).
- 2026-10-19..21 — **Full run, 10^6 ledger** (log `full_run_20261019.out`): hard cap hit in Exp. 4 S1, finished with a resume (`resume_20261021.out`); coverage 380/380, 0 tracebacks. Results `Benchmark/results/<exp>/<method>/experiment/`; history_id `bd71900b56549308`, saved histories server-only `results/_histories/`. ~US$60.
- 2026-10-21 — Exp. 4 VeRedact-PQ slowed by the auditor scanning the chain since deployment; fixed: read only anchoring blocks (`anchor.py` `cp_block`). Old rows `results/_superseded_20261021_exp4_logscan/` (server). Rerun log `exp4_rerun_20261021.out`: done 21 Oct 16:29 UTC, 500/500 ok, coverage 380/380; fetched (laptop old rows also in `_superseded_20261021_exp4_logscan/`).
- 2026-10-21 — Blue manuscript: Exp. 1, 2, 3, 5 and both tables from the 10^6 run (`Overleaf/revised/`). Exp. 4 text pending the rerun.
- 2026-10-22 — Workspace cleanup: `resume_run.sh` -> `RESUME=1 full_run.sh`; `check_chain_reads_besu.py` -> Besu-only test in `tests/test_history.py`; `fill_history` removed; docs rows updated; `fetch_results.sh` skips `_histories`.
- 2026-10-23 — Exp. 1 rates (author): 1, 2, 4, 10, 25, 50, 100, 250, 500, 1,000 req/s for every scheme (2,000/5,000 dropped, manuscript changed); latency drawn only where full; client join on one deadline. Code only, not run; rerun of all five schemes pending.
- 2026-10-24 — Blue manuscript: Exp. 4 text + figure from the rerun; `perf_analysis_blue.tex` re-extracted; PDF not recompiled.
- 2026-10-24 — Manuscript switched to `Overleaf/VeRedact-optimize.tex` (author). Protocol updated test-first (`tests/test_protocol.py`): Phase 3 state digest h_st, CORA selector (`protocol/cora.py`), Gamma_e plan + P_exec in P_auth, SFMR Theta_b/Xi_b, SAVER audit (VCS reuse, per-request escalation, Shared-Evidence/Per-Record modes). Laptop test env added (Python 3.12 + Rust, `Benchmark/.venv`); 13 local failures are Windows-only (forkserver, /proc/cpuinfo). Next: ablations, experiments, reporting.
- 2026-10-24 — Experiments rebuilt for VeRedact-optimize.tex: ablation variants (`veredact-<variant>`), Exp. 1 CORA rounds + skew metrics (|Omega_e|, adaptations, F_e), Exp. 2 Phase 4 + Re-ZK, Exp. 3 SAVER efficiency (sharing axis 1/8/64, verified nodes), Exp. 4 escalation 0-100 % + fault classes, Exp. 5 `exp05_blockchain_overhead` (tx size + finality, validators 4/7/10; gas and tab_gas removed); 10^5 ledger, n_Q to 10^4, rates 100-5,000; figures redrawn; checked by tests and local smoke (results never). Docs + HANDOFF updated.
- 2026-10-26 — Check boot (server): ruff ok; pytest 101 passed (Besu test incl.); `make smoke FORCE=--force` 0 errors, coverage 123/123 (log `smoke_force_20261026.log`). Fixed: `remote.sh` rsync `--delete` (stale exp05_gas files broke validate); `full_run.sh` provers for all four Exp. 1 VeRedact-PQ systems.
- 2026-10-27 — Scale run 2026-10-26 (`results/logs/scale_run_20261026.out`): nothing measured; validate refused dead `tiers/scale.yaml` n_Q=10^5 sample overrides. Removed them; `validate_config.py scale` 0 errors. Author: no scale rerun (option C), go to the full run.
- 2026-10-27 — Author: 5 full runs on 5 machines (spot). `VeRedact-optimize.tex` (author asked): "repeated 30 times"/"30 runs" -> 5 independent runs. `rep_exp1_veredact.sh`/`rep_run.sh`: all four Exp. 1 prover systems, caps 26/27/24 h.
- 2026-10-27 — ~10 h target: each repetition on 3 spot workers (`rep_run.sh <rep> a|b|c`: Exp. 0/1/2/5 · Exp. 3/4 VeRedact-PQ+S1 · Exp. 3/4 S13), `launch_reps.sh` PARTS; spot workers (`provision_workers.sh`, teardown cancels requests); coordinator/prover caps R x 2.5 h.
- 2026-10-27 — Author: ONE run first (5 runs decided later). `single` mode in `launch_reps.sh`/`rep_exp1_veredact.sh`/`rep_run.sh`/`collect_reps.sh` (results/.../experiment/, rep 1's seed); `supersede_results.sh` moves older experiment(-repNN) folders aside at launch; `SKIP_TABLES=1` on split parts. Paper still says 5 runs.
- 2026-10-28 — Author: 1 run only, us-east-2, fair split by experiment (`rep_run.sh` e1/e2/e3/e4/e05; e1 = all Exp. 1 systems on one machine, provers launched from the laptop by `provision_provers.sh REGION/SYS_IID`, spot). `aws.toml [run] region`; workers/teardown/collect/refresh_ssh in the run region; `rep_exp1_veredact.sh` removed (unfair coordinator split). Not run on AWS.
- 2026-10-28 — `VeRedact-optimize.tex` (author asked): repetitions -> one run, 30 samples per point (100 Exp. 0, 5 for S13 at n_Q = 10^4, every request in Exp. 1); Table params "1 run, 30 samples per point, 95% CI".
- 2026-10-28 — Plan C (author, grilled): 3 runs, us-east-2, one e1 worker for Exp. 1 of all runs + 12 workers (one per part and run); `utils/run_plan.py`, `tests/test_run_plan.py`.
- 2026-10-28 — Provers m7i.48xlarge -> c7i.48xlarge spot -> on demand, zone us-east-2a, prebuilt image (`build_image.sh`); run caps in `configs/aws.toml [run]`.
- 2026-10-28 — Fixed `provision_provers.sh`: from macOS it never started the prover service (`timeout` missing); now fails unless every prover listens.
- 2026-10-28 — Setup profile at 10^5 (server): VeRedact-PQ 32 s/point, S13 28 s, S27 12 s, S34 ~82k targets x 43 ms (~59 min/run); setup reuse/parallel dropped.
- 2026-10-28 — Paper: three independent runs, mean over runs, 95% CI (t, 2 df).
- 2026-10-28 — Review fixes (two-axis code review): bash 3.2 empty arrays, key import, e1 alone in its zone, set-up caps, builder cleanup, prover region teardown, coverage gaps on e1, smoke collect, 3-run floor, ONLY/FORCE reruns, image tied to its commit.
- Open: no run with the new code yet (check boot, then full run; cost of 30 repetitions to estimate); Fixed-Batch vs CORA throughput to watch; S13 witness timing 3-7 % high; old server results to move aside (author yes needed).
- 2026-10-30 — Smoke of plan C (us-east-2): image built (c9cdad1, 105 tests), 13 workers, 12 parts exit 0; e1 not run. Fixed: prover disk < image snapshot; prover start hung ssh (subshell); openrsync ignores dir/** (now ***); stale smoke folders (supersede per tier); test_fidelity leaked prover workers (veredact-bench up 36.6 h, ~US$47); spot workers one per request; launch restarts stopped workers. Not committed.
- 2026-10-30 — Final plan (author): two e1 workers (runs 1+3 | 2) each with its own prover pair, 14 workers, spot only (no on-demand fallback; no spot: nothing starts), provers try every zone and the e1 worker follows; `run_plan.py` [run] e1_machines; build_image replaces the old image. ~8 h, ~US$35–50.
