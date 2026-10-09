# VeRedact-PQ experiments — rules, boundaries, systems

How the evaluation in `overleaf/VeRedact-2.tex` Sec. Evaluation is produced (the manuscript is final; text it
needs goes to `overleaf/newchange.md`). Same method as the conference
artefact (ZK-Redact): real execution, one config, one dataset, one contract for every system.

## 0. Rules (enforced, not aspirational)

| # | Rule | Enforced by |
|:--|:--|:--|
| 1 | **Real execution only.** No simulated timings, analytical cost models, busy-waits or extrapolation. Every number comes from running the code. | code review; there is no simulator in the repo |
| 2 | **No hardcoded parameters.** Every value is in `configs/` (composed per run: base + dataset + methods + experiment + tier; comparison) or `configs/methods/<scheme>.yaml` `reproduction` (each paper's own figures). | `validate_config` key-set check; no `cfg.get(key, default)` |
| 3 | **No magic numbers.** Every config value carries a marker and a rationale: `[DERIVED]` `[METHOD]` `[PROPOSED]` `[MEASURED]` `[CONFIRM]`. | review; `grep -rn CONFIRM configs/` |
| 4 | **One dataset, one trace, one config for all systems.** `dataset.build_dataset` is seeded; its digest (`dataset_id`) is in every manifest. | `results.RunWriter` |
| 5 | **Reproducible.** Seed, resolved config, git commit + dirty flag, environment fingerprint (CPU, cores, signature backend) recorded per run; rows are per request, never pre-aggregated. | `results.RunWriter` |
| 6 | **Crypto time and ledger time are never summed.** Separate columns (`*_crypto_ms`, `*_ledger_ms`, `finality_ledger_ms`). | `scheme.RedactionResult` |
| 7 | **Capabilities beside every number.** Each row carries `cap_*` columns reported by the implementation; every figure prints them. | `Scheme.capabilities()`, `plot.caption` |
| 8 | **Nothing synthesised.** An operation a paper does not define raises `NotSupported` and is recorded as such (S27/S34 audit). | `scheme.NotSupported` |
| 9 | **Equal security.** Baselines at 128-bit classical (RSA ≥ 3072, BLS12-381); VeRedact-PQ at NIST level 3. The experiment tier refuses weaker parameters, the in-process ledger, and any ML-DSA backend but liboqs. | `validate_config`, `__main__.cmd_run` |
| 10 | **Fidelity tests.** Each system must reject exactly what its paper can reject. | `tests/test_fidelity.py`, `make test` |

Config tiers have identical keys: `smoke` (server, minutes, in-process ledger) → `pilot` (server, Besu,
resolve sweep bounds, measure variance) → `experiment` (paper numbers). `make validate-config CONFIG=…`
gates every run; the CLI refuses an invalid config.

## 1. The contract (`src/veredact_bench/methods/scheme.py`)

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
| `veredact` | VeRedact-PQ; internal variants `veredact:per_request`, `veredact:fixed_batch`, `veredact:no_bimc` (Exp. 1), `veredact:re_zk` (Exp. 2), `veredact:per_record_evidence` (Exp. 3) as the manuscript describes | `src/veredact_bench/methods/veredact/` | this file |
| `S1` | Li et al. [1] Improved DCH on Jia's chain | `src/veredact_bench/methods/baselines/s01_improved_dch/adapter.py` | `docs/baselines/S1-improved-dch.md` |
| `S13` | Zhang et al. [13] EAQ-VRBC | `src/veredact_bench/methods/baselines/s13_eaq_vrbc/adapter.py` | `docs/baselines/S13-eaq-vrbc.md` |
| `S27` | Liu et al. [27] ETCH | `src/veredact_bench/methods/baselines/s27_etch/adapter.py` | `docs/baselines/S27-etch.md` |
| `S34` | J. Xue et al. [34] REBS | `src/veredact_bench/methods/baselines/s34_rebs/adapter.py` | `docs/baselines/S34-rebs.md` |

VeRedact-PQ primitives are all real: ML-DSA-65 (liboqs on the server), SIS chameleon hash with MP12 gadget
trapdoor and dealerless t-of-n distribution (`crypto/pqch_sis.py`), winterfell STARK over a Rescue-Prime
credential registry (`native/pqzk_stark`, 128-bit conjectured soundness), SHA3-256 / HMAC-SHA3-256.
The STARK proves the manuscript's R_P: credential membership (revocation = removal from the registry) and
expiry > ts_r (ValidCred), leaf bound to the requester (RequesterBound), and attribute ≥ the policy
threshold bound in C_P (PrivatePolicy), the last two predicates as 32-bit range proofs in the AIR.

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

## 3. Experiments (`src/veredact_bench/evaluation/experiments/`, configs `configs/experiments/<id>.yaml`)

| Exp | Fig. | Systems (config) | What is measured | Notes |
|:--|:--|:--|:--|:--|
| exp00_primitives | tab:primitives | VeRedact-PQ + each baseline's own primitives | per-operation time, `samples_per_point` calls, fresh inputs | VeRedact-PQ on the protocol's own Crypto facade; baselines on their construction modules at `[baselines.*]` parameters |
| 1 | 3 | all five | open-loop, real time: per-request latency submit → finalized, goodput, per-stage times | client threads prove at arrival; VPS worker pool; ABRRR batcher (B_e\* from λ̂, T_max); stale requests returned for revalidation (manuscript Phases 4/5); every system runs every rate (no early stop; author rule 2026-10-05); a point is noted saturated when decided/offered or on-time < 1 − tol; throughput = redactions finalized during the window; `decided`, `revalidations`, `submitted_on_time` reported per point |
| 2 | 4 | veredact, S1, S34 | Phase 3 per request + Phase 4 per batch, split into attestation / freshness / commitment / committee; baselines' own authorization | committee axis maps to each system's own distribution parameter (S1 nodes, S34 policy attributes); baselines have no batch axis (b = 1). S13 (key possession) and S27 (threshold only inside Adapt) define no authorization step |
| 3 | 5 | veredact, S13, S1 | audit response generation time + size vs n_Q; VeRedact-PQ and Per-Record Evidence at 1, 4, 16, 64 returned records per authorization batch | n_Q above a system's history is recorded `unreachable` (S1: one redaction per block) |
| 4 | 6 | veredact, S13, S1 | auditor verification time split by step (Fig. 6(b)); VeRedact-PQ normal and deep audit (baselines: their one level); injected modified/substituted/stale records | per-record decisions written; S13's aggregate decision shows as false rejections |
| 5 | 7, VIII | all five | gas from Besu receipts per on-chain transaction, Zipf skews 0 and 0.8 | anchor receipt log; no receipts on the in-process ledger (refused in the experiment tier) |

Rows 1–5 above are `exp01_redaction_throughput` … `exp05_gas_consumption`. Figures draw what the manuscript's
experiment text describes (author decision 2026-10-09): VeRedact-PQ, Schemes [1], [13], [27], [34], and that
experiment's internal variants, deep audit (Fig. 6) and both skews (Fig. 7). One run per configuration point
(no repetitions): Exp. 1 statistics come from every request of the run, Exp. 2–4 from `samples_per_point`
batches / queries inside it.

Outputs: `results/<experiment>/<method>/<tier>/` with `rows.csv`, `metrics.json`, `config_resolved.yaml`,
`run_info.json`, `run.log` (a finished method is skipped unless `--force`); `make tables figures` writes
`paper/tables/*.tex` and `paper/figures/*.pdf` (mapping: `paper/MANIFEST.md`). Each baseline's own paper
evaluation: `make paper-runs` → `results/reproduction/<S id>/*.csv`.

## 4. Known measurement limits

- **Round-vectorised PQCH adaptation.** In an ABRRR round every touched batch's (p_j, z_j) is fixed
  before any member is asked, so each member returns S_k Z for the whole round in one matrix product
  (exact in float64; checked bound) instead of one 134 MB pass per batch — the same PartAdapt, linear in z.
  All t members run on this one host and share its cores and memory bandwidth, which is conservative
  against t separate nodes. Measured at full size: 28 → 135 redactions/s execution capacity (laptop).
- **Pipelined anchoring for every system.** No system blocks on a receipt before its next redaction:
  VeRedact-PQ and all four baselines hand back a finality Future; Exp. 1 latency ends when the block
  holding the transaction is observed (one block watcher, `ledger.receipt_poll_ms`). None of the baseline
  papers requires one transaction per block, so serialising them would be a strawman. Besu's pool admits
  thousands of in-flight transactions from the one sender (`configs/aws.toml [besu].tx_pool*`).
- **Setup reuse.** Data-owner keys and their ML-DSA signatures over the seeded commitments D_i are made
  once per process and reused by every setup (Exp. 1 re-runs setup per point); the PBN verifies each
  signature when it is first made. Setup is untimed, so no measured number changes.
- **Committee key reuse.** The SIS-PQCH DKG (untimed setup, 5 s at n = 4, ~5 min at n = 32 with 134 MB
  shares) runs once per (seed, n, t, lattice parameters) and is cached in `.cache/pqch_dkg/`
  (gitignored), as a committee runs DKG once per epoch. All points of a run therefore share
  one committee key per committee size; adaptation cost does not depend on the key's values. DKG draws from
  its own random stream, so a cache hit changes no other randomness.

- **GIL.** VPS workers are Python threads. ML-DSA (liboqs, ctypes) and the STARK (Rust, `allow_threads`)
  release the GIL; Python glue does not. Exp. 1 throughput is therefore a property of this implementation
  on the stated host, recorded as such — not of the protocol in the abstract.
- **Single host.** Load generator, VPS, committee and Besu validators share one instance
  (`[environment]`). The client shortfall is measured (`client_lag_ms`, achieved offered rate) and a
  client-bound point stops the sweep with a note instead of being reported as saturation. Each STARK
  proof runs single-core on its requester thread (winterfell without `concurrent`), 16 requester threads.
- **Freshness instability.** A request binds its batch version; under Zipf hot batches a point can tip into
  a re-prove/resubmit storm by chance (pilot 2026-10-04: same point 17–61 % or 100 % decided). Reported,
  not hidden: `decided`, `revalidations` per point.
- **pqcrypto vs liboqs.** The laptop fallback signs ML-DSA-65 in ~8.7 ms (liboqs: well under 1 ms); smoke
  numbers are plumbing checks only. The experiment tier refuses any backend but liboqs.
