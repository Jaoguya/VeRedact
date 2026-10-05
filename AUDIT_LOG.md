# AUDIT_LOG — VeRedact-PQ evaluation code

Audit of the simulation/evaluation code against the manuscript (`overleaf/VeRedact-2.tex`, mirrored in
`overleaf/VeRedact.md`). Rules: no fabricated or tuned numbers; paper preferred over code, every discrepancy
listed; work on `main` (author decision 2026-10-05, no branch), local commit after each verified fix, push on
"commit push"; all compute on the AWS server (`deploy/aws/remote.sh`); small configuration first; no capped
figure lines. Unexplained mismatches are reported with evidence, not papered over.

## Phase 0 — Recon (2026-10-05)

### Environment (server `veredact-bench`, ap-southeast-1)

| Item | Value |
|:--|:--|
| Instance | c7i.4xlarge, Intel Xeon Platinum 8488C, 16 vCPU (8 cores × 2 threads), 30 GiB |
| OS / Python | Ubuntu 24.04 (kernel 7.0.0-1013-aws), Python 3.12.3 |
| Ledger | 7 × Hyperledger Besu 25.6.0 QBFT (Docker 29.1.3), block 2 s, netem 10 ms |
| Key packages | numpy 2.5.3, scipy 1.18.1, gmpy2 2.3.1, cryptography 50.0.1, coincurve 21.0.0, web3 8.0.0, omegaconf 2.3.0, matplotlib 3.11.2, pytest 9.1.1, ruff 0.16.10; liboqs ML-DSA-65; winterfell 0.13 (single-core) |

### Entry points and data flow

| Stage | Location |
|:--|:--|
| Config | `configs/base.yaml` + `datasets/` + `methods/` (VeRedact-PQ, S1, S13, S27, S34) + `experiments/exp00..05` + `tiers/{smoke,pilot,experiment}` (OmegaConf), gate `scripts/validate_config.py` |
| Run | `make all TIER=…` → `scripts/run_eval.py` → `evaluation/runner.py` → `evaluation/experiments/exp0X_*.py` |
| Schemes | `methods/veredact/{crypto,ds,protocol}` (Phases 1–6), baselines `methods/baselines/s{01,13,27,34}_*/{construction,adapter}.py`, one `Scheme` contract (`methods/scheme.py`) |
| Ledger | `evaluation/anchor.py` (Besu QBFT or in-process), contracts `contracts/*.sol` |
| Raw results | `results/<exp>/<method>/<tier>/{rows.csv, metrics.json, run_info.json, config_resolved.yaml, run.log}` (`evaluation/results.py`) |
| Metrics | `evaluation/summaries.py` (per point) using `metrics/` (pure functions, scipy t-CI) |
| Figures / tables | `reporting/{figures,tables}.py` → `paper/figures/*.{pdf,png}`, `paper/tables/*.tex` |
| Diagnostics | `scripts/review_outputs.py`, `scripts/diag_core_isolation.py`, `scripts/resummarize.py` |

### Baseline wall-clock (experiment tier, 2026-10-04/05, from `run_info.json`)

| Exp | VeRedact-PQ | S1 | S13 | S27 | S34 |
|:--|:--|:--|:--|:--|:--|
| 0 primitives | 24 s | 1 s | 13 s | 0 s | 15 s |
| 1 throughput (old early-stop rule) | 916 s | 806 s | 792 s | 1,262 s | 4,832 s |
| 2 authorization | 2,223 s | 46 s | — | — | 62 s |
| 3 audit | 710 s | 950 s | 2,733 s | — | — |
| 4 verification | 2,154 s | 3,476 s | 2,639 s | — | — |
| 5 gas | 407 s | 38 s | 439 s | 23 s | 307 s |

≈ 9.4 h of measurement in total (plus setup). The no-cap changes (commit b228d25) add Exp. 1 rates for every
system, baselines at every m in Exp. 2/5 and S1 to n_Q = 10^4: projected ≈ 13–15 h — above the 12 h target,
so Phase 3 applies.

### Paper element → code → status

| Paper element | Code | Status |
|:--|:--|:--|
| Phase 1 init: ML-DSA-65, SIS-PQCH t-of-n (MP12), STARK (transparent) | `crypto/pqsig.py`, `crypto/pqch_sis.py`, `crypto/pqzk_stark.py` + `native/pqzk_stark` | implemented; PQCH construction is `[TBD: confirm]` in the paper |
| Phase 2 commitment: batches of N leaves, SA-RLI shards S | `protocol/veredact.py` (Ledger), `ds/merkle.py`, `ds/index.py` | implemented |
| Phase 3 request validation (VPS): 2T_V + T_ZV + T_S + T_PRF + O(log)T_H | `VeRedactPQ.validate` | implemented |
| Phase 4 ABRRR + committee: m T_V + t(T_S+T_V) + O(m)T_H | `target_batch_size`, `VeRedactPQ.authorize` | implemented |
| Phase 5 BIMC execution: \|Ω_e\|(t T_PA + T_CB + T_CH + T_S) | `VeRedactPQ.execute` | implemented — see A3 (round cost) |
| Phase 6 audit: (n_Q + t\|Ω^B\| + 1)T_V + O(n_Q log N_A)T_H; state-transition adds O(\|Ω_e\|)T_CH | `VeRedactPQ.audit`, `verify_audit` | **mismatch A2** |
| Table IV/V baselines S1/S13/S27/S34 | `methods/baselines/*`, `docs/baselines/*.md` | implemented; deviations listed per scheme |
| Table VI primitives | `exp00_primitives.py` → `tab_primitives.tex` | measured |
| Table VII defaults (n/t 7/5, B 8/256, T_max 500 ms, N 256, S/S_A 16, ledger 10^5, s 0.8) | `configs/base.yaml`, `configs/methods/veredact.yaml` | match |
| Table VII "30 runs, 95 % CI" | one run per point, 30 samples inside the run (author decision D8) | documented deviation (`newchange.md` D1–D3) |
| Exp. 1 rates [100]–[5,000], s ∈ {0,0.4,0.8,1.2} at a fixed rate; latency submit→finalization; throughput = finalized redactions/s | `exp01_redaction_throughput.py`, `summaries._exp01` | fixed 2026-10-05 (throughput during the window; no early stop) |
| Exp. 2 Phase 4 latency, n ∈ {4..32}, m ∈ {1..256}, per batch and amortized; breakdown attestation / freshness / commitment / committee | `exp02_authorization_latency.py` | **mismatch A1** |
| Exp. 3 n_Q ∈ {10..10^4}; generation time, response size | `exp03_audit_efficiency.py` | ok (S13 witness method documented) |
| Exp. 4 normal audit, breakdown, 1–10 % injected faults | `exp04_verification_time.py` | **mismatch A2** |
| Exp. 5 gas per round and per redaction, m ∈ {1..256} | `exp05_gas_consumption.py` | ok |

## Phase 1 — Correctness findings

| ID | Finding | Evidence | Paper says | Action |
|:--|:--|:--|:--|:--|
| A1 | Exp. 2 amortized VeRedact-PQ latency includes Phase 3 VPS validation (incl. T_ZV) | `auth_per_request_ms = a.crypto_ms + ph4/b`, where `a.crypto_ms` is `VeRedactPQ.validate` (Phase 3); full run: 1.34 ms at m = 256 vs T_V = 0.03 ms | Exp. 2 = Phase 4 only; amortized latency "approaches the per-request attestation-verification cost T_V"; Table IV authorization = m T_V + t(T_S+T_V) + O(m)T_H | **fixed 7d13cfb**: amortized = Phase 4 per batch / m; test `test_exp2_veredact_amortized_is_phase4_only`; smoke run on the server: code path ok (rows satisfy amortized = per batch / m) |
| A2 | Normal audit runs the state/PQCH check once per RECORD | `verify_audit`: `ch_verify` inside the per-record loop, `state_transition=True` by default | Table IV note: state-transition audits add O(\|Ω_e\|)T_CH — once per affected batch transition | **fixed 7d13cfb**: once per (b, MR_b', exact CH and r_b' bytes) per response; test counts T_CH = distinct transitions and a record with altered r_b' is still rejected; smoke run: code path ok |
| A3 | Exp. 1: VeRedact-PQ below S27 (17.5/s vs ~155/s) | `scripts/profile_round.py` (pilot ledger, m = 14, s = 0, in-process, alone): ~82 ms of system work per round (PQCH partials ~23 ms, ML-DSA, STARK verify, hashing; no hotspot) → ~170 redactions/s capacity. Exp. 1 full run: 338 ms per round (4×), 17.5/s. Core isolation (`results/diagnostics/core_isolation.json`): decided 41 % → 83 % when requesters get their own cores | "VeRedact-PQ sustains the highest throughput" | **root cause: testbed, not protocol** — requester STARK proving (16 threads), VPS workers, executor and Besu share 16 vCPU and one GIL; only VeRedact-PQ's requesters prove, so the contention biases Fig. 3 against it. Proposed fix: requesters in separate processes on dedicated cores (or a client instance). Awaiting author decision |
