# TASK — full-experiment tracker

Updated 2026-10-03. The manuscript (`overleaf/VeRedact-2.tex`) is final: it is never edited here; text it
needs goes to `overleaf/newchange.md`. Update the **Progress** table as each step finishes.

## 1. Progress

| # | Step | Command | Status | Result / note |
|:-:|:--|:--|:--|:--|
| 1 | Code aligned with the final manuscript | — | **done** 2026-10-03 | see §3 |
| 2 | Tests | `make test` | **done** 2026-10-03 | 21 + 15 passed |
| 3 | Local smoke (laptop, in-process ledger) | `make smoke` | **done** 2026-10-03 | 20 min; primitives + Exp. 1–5 ran, 5 figures + primitives table drawn; Exp. 1 client-bound at 50 req/s (laptop ML-DSA ≈ 8.7 ms/sign; liboqs on the server) |
| 4 | Start the server | `deploy/aws/provision_ec2.sh` | to do | c7i.4xlarge, ap-southeast-1; refreshes the SSH rule to this IP |
| 5 | Server smoke (Besu + liboqs + STARK build) | `deploy/aws/launch_run.sh smoke` | to do | first run of the new code on Besu |
| 6 | Pilot | `deploy/aws/launch_run.sh pilot` | to do | sets `zipf_rate`, checks CV for 30 repetitions (§2) |
| 7 | Full experiment | `deploy/aws/launch_run.sh experiment` | to do | primitives + Exp. 1–5; ≈ 2.5–3 days, ≈ US$ 60–70 (§4) |
| 8 | Fetch results + figures | `deploy/aws/fetch_results.sh` | to do | `results/`, `plot/*.png`, `plot/primitives_table.csv`, `plot/gas_by_operation.csv` |
| 9 | Stop paying | `deploy/aws/teardown_ec2.sh` | to do | the idle watchdog powers off after 30 min idle anyway |
| 10 | Fill the manuscript from the run | `overleaf/newchange.md` §C | to do | primitive times, gas, hardware, Exp. 1–4 result paragraphs |

Per-experiment progress of step 7 (the run writes `results/<exp>/<run_id>/manifest.json` when each finishes):

| Experiment | Manuscript | Status | Run id |
|:--|:--|:--|:--|
| primitives | tab:primitives | to do | |
| exp1 | Fig. 3 throughput / p95 latency / adaptations vs skew | to do | |
| exp2 | Fig. 4 authorization latency | to do | |
| exp3 | Fig. 5 audit efficiency | to do | |
| exp4 | Fig. 6 verification time + breakdown | to do | |
| exp5 | Fig. 7 gas + tab:gas | to do | |

## 2. Decisions still yours (before step 7)

| # | Decision | Now | Recommendation |
|:--|:--|:--|:--|
| D3a | `ledger.validators` | 7 [CONFIRM] | keep 7 (one per organisation); the manuscript's "[TBD]-validator" takes this value |
| D3b | `ledger.netem_delay_ms` | 10 [CONFIRM] | keep 10 unless the paper should model a WAN |
| D3c | `experiments.exp1.zipf_rate` | 1000 [CONFIRM] | set from the pilot: below the lowest baseline saturation rate |
| D3d | `meta.repetitions` | 30 [CONFIRM] | keep 30: the final manuscript states 30 runs |
| D4 | SIS-PQCH distributed perturbation is spherical → statistical leakage of R over many adaptations | open | state as a limitation, or implement the distributed Genise–Micciancio perturbation (cost rises) |
| D6 | SIS n = 256, q = 2^16 not checked with a lattice estimator for NIST level 3 | open | run the estimator before claiming level 3 for PQCH; does not change timings already measured |
| D7 | Exp. 1 load generator shares the host with VPS, committee and 7 Besu validators | open | watch the pilot for "client-bound" notes; if they appear, add a client instance |

## 3. What changed for the full run (2026-10-03)

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
| Primitives | new `make primitives` → tab:primitives, VeRedact-PQ and baseline primitives | tab:primitives |
| Figures | panels follow the captions (Fig. 3 throughput/p95/adaptations, Fig. 4 amortized/per-batch, Fig. 6 breakdown, Fig. 7 total/amortized gas) | figure captions |
| Laptop backend | pqcrypto ML-DSA signing retried when its rejection-sampling cap is hit (FIPS 204 loops until success) | sporadic test failure |
| Setup cost | data-owner keys and signatures cached per process (seeded salts) | Exp. 1 re-runs setup per point: saves ≈ 13 h |

Manuscript text the code now differs from: `overleaf/newchange.md` §A (cost-table cells for rc_i and the
Phase 5 Auth check, f in ABRRR, Docker wording) and §B ([TBD]s the code already fixes).

## 4. Run time and cost (estimate)

| Experiment | Points | Estimate |
|:--|:--|:--|
| primitives | 25 operations × 100 reps | minutes |
| exp1 | 8 systems/variants × 30 reps × ≤ 10 points × ≈ 90 s | ≈ 60 h |
| exp2 | 4 × 5 committee sizes × 6 batch sizes × 30 reps | ≈ 1–2 h |
| exp3 + exp4 | 10 histories × n_Q up to 10^4 × 30 reps | ≈ 4–6 h |
| exp5 | 5 systems × 2 skews × 6 batch sizes, Besu receipts | ≈ 1–2 h |

c7i.4xlarge in ap-southeast-1 ≈ US$ 0.9/h → ≈ US$ 60–70 for the experiment tier. Exp. 1 dominates; a lower
`meta.repetitions` is the only large saving, and the manuscript states 30.

## 5. Docs synced (2026-10-03, approved)

`docs/experiments.md`, `docs/paper-conformance.md`, `docs/baselines/S1-, S13-, S34-*.md`, `README.md` and the
skill file describe the code above; the superseded `overleaf/New changes.tex` was removed (its role is now
`overleaf/newchange.md`).
