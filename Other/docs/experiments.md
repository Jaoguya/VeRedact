# VeRedact-PQ experiments — rules, boundaries, systems

How the evaluation in `Overleaf/VeRedact-2.tex` Sec. Evaluation is produced (the manuscript is final; text it
needs goes to `Overleaf/newchange.md`). Same method as the conference
artefact (ZK-Redact): real execution, one config, one dataset, one contract for every system.

## 0. Rules (enforced, not aspirational)

| # | Rule | Enforced by |
|:--|:--|:--|
| 1 | **Real execution only.** No simulated timings, analytical cost models, busy-waits or extrapolation. Every number comes from running the code. | code review; there is no simulator in the repo |
| 2 | **No hardcoded parameters.** Every value is in `Benchmark/configs/` (composed per run: base + dataset + methods + experiment + tier; comparison) or `Benchmark/configs/methods/<scheme>.yaml` `reproduction` (each paper's own figures). | `validate_config` key-set check; no `cfg.get(key, default)` |
| 3 | **No magic numbers.** Every config value carries a marker and a rationale: `[DERIVED]` `[METHOD]` `[PROPOSED]` `[MEASURED]` `[CONFIRM]`. | review; `grep -rn CONFIRM Benchmark/configs/` |
| 4 | **One dataset, one trace, one config for all systems.** `dataset.build_dataset` is seeded; its digest (`dataset_id`) is in every manifest. | `results.RunWriter` |
| 5 | **Reproducible.** Seed, resolved config, git commit + dirty flag, environment fingerprint (CPU, cores, signature backend) recorded per run; rows are per request, never pre-aggregated. | `results.RunWriter` |
| 6 | **Crypto time and ledger time are never summed.** Separate columns (`*_crypto_ms`, `*_ledger_ms`, `finality_ledger_ms`). | `scheme.RedactionResult` |
| 7 | **Capabilities beside every number.** Each row carries `cap_*` columns reported by the implementation; every figure prints them. | `Scheme.capabilities()`, `plot.caption` |
| 8 | **Nothing synthesised.** An operation a paper does not define raises `NotSupported` and is recorded as such (S27/S34 audit). | `scheme.NotSupported` |
| 9 | **Equal security.** Baselines at 128-bit classical (RSA ≥ 3072, BLS12-381); VeRedact-PQ at NIST level 3. The experiment tier refuses weaker parameters, the in-process ledger, and any ML-DSA backend but liboqs. | `validate_config`, `__main__.cmd_run` |
| 10 | **Fidelity tests.** Each system must reject exactly what its paper can reject. | `Benchmark/tests/test_fidelity.py`, `make test` |

Config tiers have identical keys: `smoke` (server, minutes, in-process ledger) → `pilot` (server, Besu,
resolve sweep bounds, measure variance) → `experiment` (paper numbers). `make validate-config CONFIG=…`
gates every run; the CLI refuses an invalid config.

## 1. The contract (`Benchmark/src/veredact_bench/methods/scheme.py`)

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
| `veredact` | VeRedact-PQ (no internal variants since 2026-10-04) | `Benchmark/src/veredact_bench/methods/veredact/` | this file |
| `S1` | Li et al. [1] Improved DCH on Jia's chain | `Benchmark/src/veredact_bench/methods/baselines/s01_improved_dch/adapter.py` | `Other/docs/baselines/S1-improved-dch.md` |
| `S13` | Zhang et al. [13] EAQ-VRBC | `Benchmark/src/veredact_bench/methods/baselines/s13_eaq_vrbc/adapter.py` | `Other/docs/baselines/S13-eaq-vrbc.md` |
| `S27` | Liu et al. [27] ETCH | `Benchmark/src/veredact_bench/methods/baselines/s27_etch/adapter.py` | `Other/docs/baselines/S27-etch.md` |
| `S34` | J. Xue et al. [34] REBS | `Benchmark/src/veredact_bench/methods/baselines/s34_rebs/adapter.py` | `Other/docs/baselines/S34-rebs.md` |
| `S99` | Q. Li et al. LETA (post-quantum batch authentication; Exp. 0 and 2 only) | `Benchmark/src/veredact_bench/methods/baselines/s99_leta/adapter.py` | `Other/docs/baselines/S99-leta.md` |

VeRedact-PQ primitives are all real: ML-DSA-65 (liboqs on the server), SIS chameleon hash with MP12 gadget
trapdoor and dealerless t-of-n distribution (`crypto/pqch_sis.py`), winterfell STARK over a Rescue-Prime
credential registry (`Benchmark/native/pqzk_stark`, 128-bit conjectured soundness), SHA3-256 / HMAC-SHA3-256.
The STARK proves the manuscript's R_P: credential membership (revocation = removal from the registry) and
expiry > ts_r (ValidCred), leaf bound to the requester (RequesterBound), and attribute ≥ the policy
threshold bound in C_P (PrivatePolicy), the last two predicates as 32-bit range proofs in the AIR.

### Capability matrix (generated: `make capabilities`)

| capability | veredact | S1 | S13 | S27 | S34 | S99 |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|
| pq_security | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| distributed_auth | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| policy_control | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ |
| batch_redaction | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| private_verification | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ |
| verifiable_auditing | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| state_freshness_check | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| consensus_bound_auth | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

Where this differs from manuscript Table I, the code is right and the table must change
(`Other/docs/paper-conformance.md` §2).

## 3. Experiments (`Benchmark/src/veredact_bench/evaluation/experiments/`, configs `Benchmark/configs/experiments/<id>.yaml`)

| Exp | Fig. | Systems (config) | What is measured | Notes |
|:--|:--|:--|:--|:--|
| exp00_primitives | tab:primitives | VeRedact-PQ + each baseline's own primitives (S99: NTT product, Sign + ZKP, ZKP verify, aggregation and Eq. 13 at m = `reference_batch`) | per-operation time, `samples_per_point` calls, fresh inputs | VeRedact-PQ on the protocol's own Crypto facade; baselines on their construction modules at `[baselines.*]` parameters |
| 1 | 3 | veredact, S1, S13, S27, S34 | open-loop, real time: end-to-end latency arrival → finalized over every window arrival (a request not finalized by the point's cutoff `cutoff_s`, the end of the drain, enters censored at cutoff − arrival: a lower bound, hollow marker in Fig. 3(b); 2026-10-16), goodput, per-stage times | client threads prove at arrival; VPS worker pool; ABRRR batcher (B_e\* from λ̂, T_max); stale requests returned for revalidation (manuscript Phases 4/5); every system runs every rate (no early stop; author rule 2026-10-05), 1–1,000 req/s so the low end is below every scheme's capacity (2026-10-23); latency drawn only where it is a full measurement; a point is noted saturated when decided/offered or on-time < 1 − tol; throughput = redactions finalized during the window; `decided`, `revalidations`, `submitted_on_time` reported per point |
| 2 | 4 | veredact, S1, S34, S99 | COMPLETE authorization (2026-10-17): per request = per-request step (VeRedact-PQ Phase 3 validation; a baseline's whole authorization; S99 PL identity check) + batch step / m (VeRedact-PQ Phase 4; S99 aggregation + Eq. 13); per batch = m per-request steps + batch step (`auth_complete_*` in metrics.json). Phase 4 alone left out VeRedact-PQ's ~1.3 ms validation while counting the baselines' whole authorization | committee axis maps to each system's own distribution parameter (S1 nodes, S34 policy attributes; S99 none, flat in n); S1 and S34 have no batch protocol (drawn dashed). S13 (key possession) and S27 (threshold only inside Adapt) define no authorization step |
| 3 | 5 | veredact, S13, S1 | audit response generation time + size vs n_Q ∈ {10, …, 10^5} (VeRedact-PQ at batch size `reference_batch`) | every scheme applies the same untimed history list (`data/history.py`, `history_id` in every row) reaching the largest n_Q; histories are saved and reloaded behind safeguards (`evaluation/history_cache.py`); Exp. 4 reuses Exp. 3's in-process history (`exp03_audit_efficiency.SHARED`) |
| 4 | 6 | veredact, S13, S1 | auditor verification time vs n_Q ∈ {10, …, 10^5} (per-step breakdown kept in rows/metrics, not drawn); normal audit; injected modified/substituted/stale records; auditors read the chain (`anchor.read`): VeRedact-PQ its anchored checkpoints from their anchoring blocks, S1 its anchored accumulator and records, S13 its accumulator from the trusted node | per-record decisions written; S13's aggregate decision shows as false rejections; detection rate is empty (None) when f · n_Q rounds to 0 injected records |
| 5 | 7, VIII | veredact, S1, S13, S27, S34 | gas from Besu receipts per on-chain transaction, skew `workload.zipf_s` | anchor receipt log; no receipts on the in-process ledger (refused in the experiment tier) |

Rows 1–5 above are `exp01_redaction_throughput` … `exp05_gas_consumption`. Figures (2026-10-17): Fig. 3 = throughput + p95 end-to-end latency only (the skew sweep still runs, its PQCH-adaptation count stays in metrics.json, not drawn: the baselines have no batches); Fig. 6 = verification time only (breakdown in rows/metrics); Fig. 7 = (a) gas per redaction per scheme (VeRedact-PQ at m = 1 and at `reference_batch`), (b) VeRedact-PQ vs m with the cheapest baseline as a reference line — no baseline is drawn against a batch axis it does not have. Log axes are labelled a × 10^k. Figures draw exactly one line per scheme
(VeRedact-PQ, Schemes [1], [13], [27], [34], and LETA in Exp. 0 and 2); there are no internal variants and no second setting of a
scheme (author decisions 2026-10-04, following the ZK-Redact evaluation, where ablations are points of the
scheme's own sweep, e.g. batch size m = 1 in Exp. 2). One run per configuration point (author decision
2026-10-19; the 10-repetition plan of 2026-10-17 was revoked, its tooling `VRPQ_REP` / `scripts/aggregate_reps.py`
stays optional): Exp. 1 statistics come from every request of the run, Exp. 2–4 from 30 batches / queries per
point, except 5 at n_Q = 10^5 for every scheme and 5 for S13 at n_Q = 10^4 (one query costs minutes to hours).

Ledger (2026-10-18, author decision): 10^6 synthetic transactions (`configs/datasets/synthetic_ledger.yaml`; manuscript
setup table: 10^5), so the audit axis reaches n_Q = 10^5 for every scheme. S1 uses blocks of one transaction
(`Other/docs/baselines/S1-improved-dch.md`).

Outputs: `Benchmark/results/<experiment>/<method>/<tier>/` with `rows.csv`, `metrics.json`, `config_resolved.yaml`,
`run_info.json`, `run.log` (a finished method is skipped unless `--force`); `make tables figures` writes
`Overleaf/tables/*.tex` and `Result/Pdf/*.pdf` (mapping: `Other/docs/paper-manifest.md`). Each baseline's own paper
evaluation: `make paper-runs` → `Benchmark/results/reproduction/<S id>/*.csv`.

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
  thousands of in-flight transactions from the one sender (`Benchmark/configs/aws.toml [besu].tx_pool*`).
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
- **Ledger capacity.** The Besu network (7 QBFT validators, 2 s blocks, one sending account, same host)
  confirms about 150 anchoring transactions/s. A scheme that sends one transaction per redaction above that
  rate builds a ledger backlog (S27, full run 2026-10-16: confirmation 3 s → 201 s over a 500 req/s point);
  receipts that arrive after the cutoff are censored, not counted at full value. VeRedact-PQ sends one per batch.
- **pqcrypto vs liboqs.** The laptop fallback signs ML-DSA-65 in ~8.7 ms (liboqs: well under 1 ms); smoke
  numbers are plumbing checks only. The experiment tier refuses any backend but liboqs.
