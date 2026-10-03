# TASK — full-experiment tracker

Updated 2026-10-03. The manuscript (`overleaf/VeRedact-2.tex`) is final: it is never edited here; text it
needs goes to `overleaf/newchange.md`. Update §1 and the run ledger (§1.1) as each step finishes.

## 1. Progress

Rule: when a step finishes, set **Status** to `done <date>` and write in **Result stored at** the exact path
it produced. `results/` is gitignored: it exists only on the machine that ran it (this laptop or the EC2
instance) and is **not on GitHub**; `paper/` (generated tables + figures) is committed.
`deploy/aws/fetch_results.sh` copies the server's `results/` and `paper/` into this checkout.

| # | Step | Command | Status | Result stored at |
|:-:|:--|:--|:--|:--|
| 1 | Code aligned with the final manuscript | — | **done** 2026-10-03 | commit `c86a97d` (what changed: §3) |
| 2 | Restructure to the IEEE evaluation-code layout (option B: YAML configs, `src/`, one run per point) | — | **done** 2026-10-03 | this commit (what changed: §3.2) |
| 3 | Tests | `make test` | **done** 2026-10-03 | console only: 44 passed |
| 4 | Local smoke from a fresh `.venv` (laptop, in-process ledger) | `make all TIER=smoke FORCE=--force` | **done** 2026-10-03 (11 min, no errors) | laptop: `results/<exp>/<method>/smoke/` (§1.1); `paper/tables/*.tex`, `paper/figures/*.pdf` (smoke numbers, not for the paper) |
| 5 | Start the server | `deploy/aws/provision_ec2.sh` | to do | instance id → `deploy/aws/.instance` (gitignored) |
| 6 | Server smoke (Besu + liboqs + STARK build) | `deploy/aws/launch_run.sh smoke` | to do | server: `results/<exp>/<method>/smoke/`, log `results/logs/smoke_*.log` |
| 7 | Pilot | `deploy/aws/launch_run.sh pilot` | to do | server: `results/<exp>/<method>/pilot/`, log `results/logs/pilot_*.log` |
| 8 | Full experiment | `deploy/aws/launch_run.sh experiment` | to do | server: `results/<exp>/<method>/experiment/`, log `results/logs/experiment_*.log` |
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
| 2026-10-03 | smoke | laptop | exp00_primitives | `results/exp00_primitives/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (smoke) |
| 2026-10-03 | smoke | laptop | exp01_redaction_throughput | `results/exp01_redaction_throughput/<method>/smoke/` — S1, S13, S27, S34, veredact, veredact-fixed_batch, veredact-no_bimc, veredact-per_request | **current** (smoke) |
| 2026-10-03 | smoke | laptop | exp02_authorization_latency | `results/exp02_authorization_latency/<method>/smoke/` — S1, S34, veredact, veredact-re_zk | **current** (smoke) |
| 2026-10-03 | smoke | laptop | exp03_audit_efficiency | `results/exp03_audit_efficiency/<method>/smoke/` — S1, S13, veredact, veredact-per_record_evidence | **current** (smoke) |
| 2026-10-03 | smoke | laptop | exp04_verification_time | `results/exp04_verification_time/<method>/smoke/` — S1, S13, veredact | **current** (smoke) |
| 2026-10-03 | smoke | laptop | exp05_gas_consumption | `results/exp05_gas_consumption/<method>/smoke/` — S1, S13, S27, S34, veredact | **current** (smoke (no gas: in-process ledger)) |
| — | pilot | EC2 | all six | `results/<exp>/<method>/pilot/` | to do |
| — | experiment | EC2 | exp00_primitives | `results/exp00_primitives/<method>/experiment/` | to do |
| — | experiment | EC2 | exp01_redaction_throughput | `results/exp01_redaction_throughput/<method>/experiment/` | to do |
| — | experiment | EC2 | exp02_authorization_latency | `results/exp02_authorization_latency/<method>/experiment/` | to do |
| — | experiment | EC2 | exp03_audit_efficiency | `results/exp03_audit_efficiency/<method>/experiment/` | to do |
| — | experiment | EC2 | exp04_verification_time | `results/exp04_verification_time/<method>/experiment/` | to do |
| — | experiment | EC2 | exp05_gas_consumption | `results/exp05_gas_consumption/<method>/experiment/` | to do |
| 2026-09-29 – 2026-10-03 | smoke | laptop | old layout | `results/{exp1..exp5,primitives}/<run_id>/`, `results/S*_*.csv` | superseded (before the restructure; never used for the paper) |

## 2. Decisions still yours (before step 8)

| # | Decision | Now | Recommendation |
|:--|:--|:--|:--|
| D3a | `ledger.validators` | 7 [CONFIRM] | keep 7 (one per organisation); the manuscript's "[TBD]-validator" takes this value |
| D3b | `ledger.netem_delay_ms` | 10 [CONFIRM] | keep 10 unless the paper should model a WAN |
| D3c | `exp01_redaction_throughput.zipf_rate` | 1000 [CONFIRM] | set from the pilot: below the lowest baseline saturation rate |
| D3d | repetitions | **decided 2026-10-03: one run per point** | manuscript text fix in `newchange.md` D1–D2 |
| D8 | new dependencies `scipy` (significance tests) and `ruff` (lint/format gate) | not added | the significance test is hand-written and tested; `ruff` would make the brief's lint gate checkable |
| D4 | SIS-PQCH distributed perturbation is spherical → statistical leakage of R over many adaptations | open | state as a limitation, or implement the distributed Genise–Micciancio perturbation (cost rises) |
| D6 | SIS n = 256, q = 2^16 not checked with a lattice estimator for NIST level 3 | open | run the estimator before claiming level 3 for PQCH; does not change timings already measured |
| D7 | Exp. 1 load generator shares the host with VPS, committee and 7 Besu validators | open | watch the pilot for "client-bound" notes; if they appear, add a client instance |

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
| Dependencies | `benchmark/requirements.txt` (unpinned) | root `pyproject.toml`, pinned; `omegaconf` added (approved) |

## 4. Run time and cost (estimate)

One run per point (2026-10-03), so the experiment tier is much shorter than the earlier 30-repetition estimate:

| Experiment | Points (one run each) | Estimate |
|:--|:--|:--|
| exp00_primitives | 25 operations × 100 samples | minutes |
| exp01_redaction_throughput | 8 systems/variants × ≤ 10 points × ≈ 100 s (window + drain + setup) | ≈ 1.5–2.5 h |
| exp02_authorization_latency | 4 × 5 committee sizes × 6 batch sizes × 30 samples | ≈ 0.5 h |
| exp03 + exp04 | 10 histories × n_Q up to 10^4 × 30 samples | ≈ 0.5–1 h |
| exp05_gas_consumption | 5 systems × 2 skews × 6 batch sizes, Besu receipts | ≈ 0.5 h |

c7i.4xlarge in ap-southeast-1 ≈ US$ 0.9/h → ≈ US$ 3–5 for the experiment tier (plus the pilot). The
estimate is replaced by the measured `runtime_s` in each `run_info.json` after the run.

## 5. Docs

`README.md`, `docs/*.md`, `docs/baselines/*.md`, the skill file and `data/README.md` describe the restructured
layout (2026-10-03).
