# VeRedact-PQ experiments — rules, boundaries, systems

How the evaluation in `overleaf/VeRedact.tex` Sec. Evaluation is produced. Same method as the conference
artefact (ZK-Redact): real execution, one config, one dataset, one contract for every system.

## 0. Rules (enforced, not aspirational)

| # | Rule | Enforced by |
|:--|:--|:--|
| 1 | **Real execution only.** No simulated timings, analytical cost models, busy-waits or extrapolation. Every number comes from running the code. | code review; there is no simulator in the repo |
| 2 | **No hardcoded parameters.** Every value is in `config/{smoke,pilot,experiment}.toml` (comparison) or `config/schemes.toml [schemes.S*.reproduction]` (each paper's own figures). | `validate_config` key-set check; no `cfg.get(key, default)` |
| 3 | **No magic numbers.** Every config value carries a marker and a rationale: `[DERIVED]` `[METHOD]` `[PROPOSED]` `[MEASURED]` `[CONFIRM]`. | review; `grep -n CONFIRM config/experiment.toml` |
| 4 | **One dataset, one trace, one config for all systems.** `dataset.build_dataset` is seeded; its digest (`dataset_id`) is in every manifest. | `results.RunWriter` |
| 5 | **Reproducible.** Seed, resolved config, git commit + dirty flag, environment fingerprint (CPU, cores, signature backend) recorded per run; rows are per request, never pre-aggregated. | `results.RunWriter` |
| 6 | **Crypto time and ledger time are never summed.** Separate columns (`*_crypto_ms`, `*_ledger_ms`, `finality_ledger_ms`). | `scheme.RedactionResult` |
| 7 | **Capabilities beside every number.** Each row carries `cap_*` columns reported by the implementation; every figure prints them. | `Scheme.capabilities()`, `plot.caption` |
| 8 | **Nothing synthesised.** An operation a paper does not define raises `NotSupported` and is recorded as such (S27/S34 audit). | `scheme.NotSupported` |
| 9 | **Equal security.** Baselines at 128-bit classical (RSA ≥ 3072, BLS12-381); VeRedact-PQ at NIST level 3. The experiment tier refuses weaker parameters, the in-process ledger, and any ML-DSA backend but liboqs. | `validate_config`, `__main__.cmd_run` |
| 10 | **Fidelity tests.** Each system must reject exactly what its paper can reject. | `benchmark/tests/test_fidelity.py`, `make fidelity-check` |

Config tiers have identical keys: `smoke` (laptop, minutes, in-process ledger) → `pilot` (server, Besu,
resolve sweep bounds, measure variance) → `experiment` (paper numbers). `make validate-config CONFIG=…`
gates every run; the CLI refuses an invalid config.

## 1. The contract (`benchmark/veredact_bench/scheme.py`)

| Method | Boundary | Timed |
|:--|:--|:--|
| `setup(dataset)` | materialise the shared corpus in the scheme's native ledger form | no (`setup_s` recorded) |
| `authorize(req)` | admission → authorization decision | yes, `auth_ms` |
| `redact(batch)` | execution → committed (crypto) → finalized (ledger receipt) | yes, crypto and ledger separately |
| `audit(query)` | service: resolve + evidence (`retrieval_ms`, `evidence_bytes`); auditor: verify (`verify_ms`) | yes |
| `capabilities()` / `auth_cost()` | what the system can do / what one authorization did | — |

Requester-side work (VeRedact-PQ: ML-DSA sign + STARK prove) is `prepare()` and is never inside an
authorization timer. The registry (`veredact_bench/registry.py`) is the only place systems are named.

## 2. Systems

| Key | System | Implementation | Boundaries |
|:--|:--|:--|:--|
| `veredact` (+ `:per_request` `:fixed_batch` `:no_bimc` `:re_zk` `:per_record_evidence`) | VeRedact-PQ | `benchmark/veredact_bench/protocol/` | this file |
| `S1` | Li et al. [1] Improved DCH on Jia's chain | `experiment/S1_ImprovedDCH/s1_baseline.py` | `docs/baselines/S1-improved-dch.md` |
| `S13` | Zhang et al. [13] EAQ-VRBC | `experiment/S13_EAQVRBC/s13_baseline.py` | `docs/baselines/S13-eaq-vrbc.md` |
| `S27` | Liu et al. [27] ETCH | `experiment/S27_ETCH/s27_baseline.py` | `docs/baselines/S27-etch.md` |
| `S34` | J. Xue et al. [34] REBS | `experiment/S34_REBS/s34_baseline.py` | `docs/baselines/S34-rebs.md` |

VeRedact-PQ primitives are all real: ML-DSA-65 (liboqs on the server), SIS chameleon hash with MP12 gadget
trapdoor and dealerless t-of-n distribution (`crypto/pqch_sis.py`), winterfell STARK over a Rescue-Prime
credential registry (`benchmark/pqzk_stark`, 128-bit conjectured soundness), SHA3-256 / HMAC-SHA3-256.

### Capability matrix (generated: `make capabilities`)

| capability | veredact | S1 | S13 | S27 | S34 |
|:--|:-:|:-:|:-:|:-:|:-:|
| pq_security | ✓ | ✗ | ✗ | ✗ | ✗ |
| distributed_auth | ✓ | ✓ | ✗ | ✓ | ✓ |
| policy_control | ✓ | ✗ | ✗ | ✗ | ✓ |
| batch_redaction | ✓ | ✗ | ✗ | ✗ | ✗ |
| private_verification | ✓ | ✗ | ✗ | ✗ | ✓ |
| verifiable_auditing | ✓ | ✓ | ✓ | ✗ | ✗ |
| state_freshness_check | ✓ | ✗ | ✓ | ✗ | ✗ |
| consensus_bound_auth | ✗ | ✗ | ✗ | ✗ | ✗ |

Where this differs from manuscript Table I, the code is right and the table must change
(`docs/paper-conformance.md` §2).

## 3. Experiments (`benchmark/veredact_bench/experiments/`)

| Exp | Fig. | Systems (config) | What is measured | Notes |
|:--|:--|:--|:--|:--|
| 1 | 3 | all five + 3 variants | open-loop, real time: per-request latency submit → finalized, goodput, per-stage times | client threads prove at arrival; VPS worker pool; ABRRR batcher (B_e\* from λ̂, T_max); stale requests returned for revalidation (manuscript Phases 4/5); saturation = decided/offered < 1 − tol stops the rate sweep; load-generator shortfall recorded separately |
| 2 | 4 | veredact, re_zk, S1, S27, S34 | Phase 3 per request + Phase 4 per batch; baselines' own authorization | committee axis maps to each system's own distribution parameter (S1 nodes, S27 redactors, S34 policy attributes); baselines have no batch axis (b = 1) |
| 3 | 5 | veredact, per_record_evidence, S13, S1 | audit response generation time + size vs n_Q, records per batch | n_Q above a system's history is recorded `unreachable` (S1: one redaction per block) |
| 4 | 6 | veredact, S13, S1 | auditor verification time; normal/deep; injected modified/substituted/stale records | per-record decisions written; S13's aggregate decision shows as false rejections |
| 5 | 7, VIII | all five | gas from Besu receipts per on-chain transaction | anchor receipt log; no receipts on the in-process ledger (refused in the experiment tier) |

Outputs: `results/<exp>/<run_id>/rows.csv` + `manifest.json`; figures `plot/exp{1..5}_*.png`
(`make plots`). Each baseline's own paper evaluation: `make paper-runs` → `results/S*_*.csv`.

## 4. Known measurement limits

- **Committee key reuse.** The SIS-PQCH DKG (untimed setup, 5 s at n = 4, ~5 min at n = 32 with 134 MB
  shares) runs once per (seed, n, t, lattice parameters) and is cached in `benchmark/.cache/pqch_dkg/`
  (gitignored), as a committee runs DKG once per epoch. All points and repetitions of a run therefore share
  one committee key per committee size; adaptation cost does not depend on the key's values. DKG draws from
  its own random stream, so a cache hit changes no other randomness.

- **GIL.** VPS workers are Python threads. ML-DSA (liboqs, ctypes) and the STARK (Rust, `allow_threads`)
  release the GIL; Python glue does not. Exp. 1 throughput is therefore a property of this implementation
  on the stated host, recorded as such — not of the protocol in the abstract.
- **Single host.** Load generator, VPS, committee and Besu validators share one instance
  (`[environment]`). The client shortfall is measured (`client_lag_ms`, achieved offered rate) and a
  client-bound point stops the sweep with a note instead of being reported as saturation.
- **pqcrypto vs liboqs.** The laptop fallback signs ML-DSA-65 in ~8.7 ms (liboqs: well under 1 ms); smoke
  numbers are plumbing checks only. The experiment tier refuses any backend but liboqs.
