# VeRedact-PQ experiments — rules, boundaries, systems

How the evaluation in `Overleaf/VeRedact-optimize.tex` Sec. Evaluation is produced (the manuscript is final; where
code and text differ: `paper-conformance.md`). Same method as the conference
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

Config tiers have identical keys: `smoke` (minutes, plumbing check only) → `experiment` (paper numbers).
`make validate TIER=…` gates every run; the CLI refuses an invalid config.

## 1. The contract (`Benchmark/src/veredact_bench/methods/scheme.py`)

| Method | Boundary | Timed |
|:--|:--|:--|
| `setup(dataset)` | materialise the shared corpus in the scheme's native ledger form | no (`setup_s` recorded) |
| `authorize(req)` | admission → authorization decision | yes, `auth_ms` |
| `redact(batch)` | execution → committed (crypto) → finalized (ledger receipt) | yes, crypto and ledger separately |
| `audit(query)` | service: resolve + evidence (`retrieval_ms`, `evidence_bytes`); auditor: verify (`verify_ms`) | yes |
| `capabilities()` / `auth_cost()` | what the system can do / what one authorization did | — |

Requester-side work (VeRedact-PQ: ML-DSA sign + STARK prove) is `prepare()` and is never inside an
authorization timer. The registry (`veredact_bench/methods/registry.py`) is the only place systems are named.

## 2. Systems

| Key | System | Implementation | Boundaries |
|:--|:--|:--|:--|
| `veredact` | VeRedact-PQ (CORA + SFMR + SAVER); ablation variants `veredact-<variant>` (VeRedact-optimize.tex, 2026-10-24): `per-request`, `fixed-batch`, `cora-no-sfmr`, `re-zk` (no longer run: #5, #6), `shared-evidence`, `per-record` (Exp. 3) | `Benchmark/src/veredact_bench/methods/veredact/` (variants: `VeRedactPQ.VARIANTS`) | this file |
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
| 1 | 3 | veredact, S1, S13, S27, S34 (#5: the ablation variants are dropped) | open-loop, real time, 20 % invalid requests (`fault_fraction` 0.2, `fault_kinds` stale + absent, #5): throughput of VALID redactions finalized in the window (the one panel), invalid requests accepted per scheme, p95 end-to-end latency (arrival -> finalized; censored at the cutoff, reported only where a full measurement), and per 1,000 redactions the PQCH adaptations, affected batches |Omega_e| and SFMR frontier nodes F_e vs Zipf skew (text) | rates 25-1,000 req/s (#5 step 2); a stale request is proved against a superseded content commitment and fails FreshLeaf; baselines have no freshness check and execute it; VeRedact-PQ systems run the Phase 4 Step 1 trigger + selection (`round_ready` / `select_round`: CORA, or the variant's arrival-order rule); baselines one request per round; stale requests re-proved; no early stop |
| 2 | 4 | veredact, S1, S34, S99 (#6: Re-ZK dropped) | complete authorization per request (Phase 3 validation + Phase 4 / m; a baseline's whole authorization) + its committee network time (`auth_with_net_per_request_ms`: one 10 ms message round per set of m for VeRedact-PQ, per request for Scheme [1]; members timed as the slowest, `methods/committee.py`; crypto alone, `auth_complete_per_request_ms`, goes to the text) vs committee size n in {4, 7, 10, 16, 32, 48, 64} at m = reference_batch (the one panel); every m at every n stays in metrics.json for the text table | committee axis maps to each system's own distribution parameter (S1 nodes, S34 policy attributes; S99 none, flat in n); S1 and S34 have no batch protocol (drawn dashed). S13 and S27 define no authorization step |
| 3 | 5 | veredact, veredact-shared-evidence, veredact-per-record, S13, S1 | response generation, size, routine verification (d_Q = 0) and verified evidence nodes vs n_Q in {10, ..., 10^4}; records per authorization batch {1, 8, 64} as the evidence-sharing axis | one untimed history list for every scheme (`data/history.py`); the audit-only variants audit VeRedact-PQ's history (`HISTORY_OF`); a fresh auditor (empty verified-context store) per query; Exp. 4 reuses Exp. 3's in-process history |
| 4 | 6 | veredact, S13, S13-per-block, S1 | verification time vs PQZK escalation fraction d_Q/n_Q in {0, 1, 5, 10, 25, 100} % (VeRedact-PQ; baselines routine only) with breakdown; then each fault class alone at 1-10 %: modified (a committed field altered), substituted (another record's genuine evidence, #8 change 3), stale (a genuine earlier transition and checkpoint of the same batch replayed, #8 change 3; a batch without an earlier version in the history falls back to an older version number); S1 and S13 bind no dependency context, so every class is one corruption for them: invalid-record rejection and valid-record acceptance. Figure (#47): one panel, routine verification vs n_Q with 1 % modified evidence — VeRedact-PQ, S1, S13 Audit then per block (`S13-fallback`), S13 Audit only (dotted); the no-fault times (VeRedact-PQ routine and deep, S1, S13 Audit, S13 per block), breakdown, other fault classes and fractions go to the text | per-record decisions written; S13's aggregate decision shows as false rejections; S13-per-block decides each block on S13's history; auditors read the chain (`anchor.read`); those reads are also reported apart (`read_ms`, #35: VeRedact-PQ 2, S1 2, S13 none as its paper names none) and Fig. 6 plots `verify_noread_ms` = `verify_ms` − `read_ms` for every system, the total stays in the text; fault positions are drawn per sample, the same for every scheme; VeRedact-PQ only (not expressible for S1 and S13, which carry no such evidence: no row): forged_approval at 1-10 % and forged_proof at `forged_proof_fraction` over every escalation fraction (routine verification never opens the proof, so detection follows d_Q/n_Q); a stale fault that falls back to an older version number is counted apart (`detection_rate_stale_version`, `detection_rate_replayed`) |
| 5 | 7 | Fig. 7: every Exp. 1 system; text table: veredact | Fig. 7 (#9, one panel): PBN anchoring transactions per finalized redaction vs arrival rate, counted inside each Exp. 1 point (anchoring submitted after setup: `anchor_tx`, `anchor_tx_bytes`, `anchor_gas`; bytes and gas per redaction for the text). Text table: VeRedact-PQ's finalization and RAI-checkpoint transaction size, gas and submission -> QBFT finalization latency vs |Omega_e| in {1, 8, 32, 64, 128}, validators {4, 7, 10} | `exp05_blockchain_overhead`; Besu restarted per validator count (`VRPQ_VALIDATORS`); in-process: payload length, no gas; finalization takes one block period and the validator sweep runs on one host (measurement limits, #9) |

Rows 1–5 above are `exp01_redaction_throughput` … `exp05_blockchain_overhead`. Figures follow the captions of VeRedact-optimize.tex: Fig. 3 valid throughput vs arrival rate (one panel, #5); Fig. 4 complete authorization per request vs n (one panel, #6); Fig. 5 end-to-end audit cost per query, generation + verification (one panel, #7; each term and the response size in metrics.json for the text); Fig. 6 verification vs n_Q (one panel, #8); Fig. 7 anchoring transactions per finalized redaction vs arrival rate (one panel, #9, from Exp. 1's points). One line per system; the ablation variants are drawn in VeRedact-PQ's colour (`reporting/style.py`). Repetitions (hybrid plan, author 2026-10-31): Exp. 2-5 in 3 runs of `ceil(samples_per_point / 3)` samples per point (`config.REPS`; seed + (r-1)·1000), combined by `scripts/aggregate_reps.py` (median: mean of the per-run medians with a Student's t CI, 2 df; p95 pooled over the runs); Exp. 0 and 1 in run 1 only (`config.ONCE`), Exp. 1 with a throughput CI over 6 sub-windows and a bootstrap p95 CI. Split over AWS workers: `Benchmark/src/veredact_bench/utils/run_plan.py`.

Ledger (2026-10-24, author: follow VeRedact-optimize.tex): 10^5 synthetic transactions (`configs/datasets/synthetic_ledger.yaml`), n_Q up to 10^4. S1 uses blocks of one transaction (`Other/docs/baselines/S1-improved-dch.md`).

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
- **Committee members and message rounds (fairness fix, #13).** The t members of VeRedact-PQ and Schemes [1],
  [27] run in one process but are timed as separate machines: a committee step's crypto time is its slowest
  member, the collector's own checks stay serial, and each message round waits a real
  `committee.message_delay_ms` (= `ledger.netem_delay_ms`), reported as network time (`*_net_ms`), never as
  crypto (`methods/committee.py`). A thread waiting on a round lets go of the Exp. 1 harness lock. In Exp. 1
  Schemes [1] and [27] keep up to `baseline_inflight` (16) redactions in flight while their messages travel,
  never two on one target, CPU still serialised; one at a time, the waits alone capped both at ~45/s (smoke
  check), a strawman. VeRedact-PQ keeps the lock through its two rounds per round of m (round e+1 builds on
  round e), which is conservative against it.
- **Requesters read a checkpoint before it is anchored (favours VeRedact-PQ).** `Ledger._checkpoint` records
  h_b^snap and the new leaves as soon as Phase 5 builds them; the anchoring transaction is submitted afterwards
  and finalizes about one block period later. A VeRedact-PQ requester (and FreshLeaf) therefore sees a
  redacted leaf ~1 block period before a requester reading the chain would, so some proofs that would go
  stale in a deployment do not (the snapshot age itself is covered by k = 8). It can only LOWER VeRedact-PQ's
  revalidations in Exp. 1, most at high rates and skew; the text states it. Baselines have no freshness check.
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
- **One host per experiment.** Load generator, VPS, committee and Besu validators share one worker
  (`[environment]`, m7i.4xlarge). VeRedact-PQ's requesters prove on a separate prover host (c8g.48xlarge,
  `evaluation/provers.py`; its first proof must verify on the system). The client shortfall is measured
  (`client_lag_ms`, `submitted_on_time`), never hidden; every rate runs for every system. Each STARK proof
  runs single-core (winterfell without `concurrent`).
- **Freshness instability.** A request binds its batch version; under Zipf hot batches a point can tip into
  a re-prove/resubmit storm by chance (pilot 2026-10-04: same point 17–61 % or 100 % decided). Reported,
  not hidden: `decided`, `revalidations` per point.
- **Ledger capacity.** The Besu network (7 QBFT validators, 2 s blocks, one sending account, same host)
  confirms about 150 anchoring transactions/s. A scheme that sends one transaction per redaction above that
  rate builds a ledger backlog (S27, full run 2026-10-16: confirmation 3 s → 201 s over a 500 req/s point);
  receipts that arrive after the cutoff are censored, not counted at full value. VeRedact-PQ sends one per batch.
- **pqcrypto vs liboqs.** The laptop fallback signs ML-DSA-65 in ~8.7 ms (liboqs: well under 1 ms); smoke
  numbers are plumbing checks only. The experiment tier refuses any backend but liboqs.
