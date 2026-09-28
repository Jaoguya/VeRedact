# TASK — status before the full run

Updated 2026-09-29. Method: the conference artefact ZK-Redact (real execution, one config, one dataset,
Scheme contract, NotSupported, fidelity tests, config tiers, gated runs). Details: `docs/experiments.md`.

## 1. Done (evidence)

| Item | Evidence |
|:--|:--|
| VeRedact-PQ Phases 1–6 on real PQ primitives: ML-DSA-65, SIS-PQCH (MP12, dealerless t-of-n, resharing), winterfell STARK | `test_core.py`: distributed adapt/reshare, t−1 shares fail, STARK rejects wrong witness/statement/requester; STARK prove 10.7 ms, verify 1.1 ms, 33.5 kB at depth 15 |
| Four baselines, each from its PDF: S1, S13, S27, S34 | `experiment/S*/s*_test.py` 15 passed; `test_fidelity.py` passed |
| Scheme contract + registry + generated capability matrix | `make capabilities` |
| Exp. 1–5 runners (real execution, per-request rows, manifest) | smoke: exp1 20,000 rows, exp2 84, exp3 23, exp4 81, exp5 717 (no gas: in-process ledger) |
| Paper-reproduction runners for all four baselines | `make paper-runs` (quick) writes `results/S*_*.csv` |
| Config tiers smoke/pilot/experiment, identical keys, validator | all three `Config is valid.` (experiment: 1 warning = [CONFIRM] count) |
| Deploy: bootstrap (liboqs + Rust/STARK), tier runner, launch + idle watchdog, Besu shape from `[ledger]` | `bash -n` clean; **not executed on AWS yet** |

Fixed during preparation: S13 audit tamper cancelled itself when two tampered records shared a block;
VPS nonce check-and-consume was not atomic under concurrent workers; Exp. 1 counted protocol
rejections (S1 one-per-block) as saturation and sampled Poisson noise as client shortfall; stale
requests were dropped instead of returned for revalidation (manuscript Phases 4/5); ABRRR T_max timer
restarted for leftover requests. Stale code and outputs removed (unused classes, dead config key
`baselines.S34.avns`, dead ABRRR queue term, old-format results).

DKG: rewritten (same output bit for bit, ~33x faster at full size; n = 32 in ~5 min instead of hours)
and cached per committee — saves ~60 h in Exp. 1 and ~2 h in Exp. 2.

## 2. Decisions that are yours

| # | Decision | Recommendation |
|:--|:--|:--|
| D1 | Rewrite the manuscript's baseline list to [1], [13], [27], [34] (Sec. Evaluation, Exp. 1–5 text, Tables IV/V) and Table I cells | do it; exact list in `docs/paper-conformance.md` §1–2. I did not edit the `.tex` |
| D2 | l. 1555 claims "identical PQ primitives across schemes"; baselines run their own classical primitives at 128-bit | change the sentence; a PQ-adapted RSA accumulator / CHET / pairing ABE is not defined by those papers |
| D3 | 8 `[CONFIRM]` values (repetitions, SIS n/k, validators, netem delay, zipf_rate) | set repetitions and zipf_rate from the pilot; validators/netem to what the paper will state |
| D4 | SIS-PQCH distributed perturbation is spherical → leaks R statistically over many adaptations | either implement the distributed Genise–Micciancio perturbation (cost rises) or state it as a limitation |
| D5 | STARK encodes credential membership + requester/statement binding, not PrivatePolicy attribute predicates | extend the AIR, or narrow the manuscript's PQZK claim |
| D6 | SIS n = 256, q = 2^16 not yet checked with a lattice estimator for level 3 | run the estimator before claiming level 3 for PQCH |
| D8 | ABRRR B̂_e = f(λ_e, \|Q_e\|, T_max) leaves f undefined (l. 576) | state f = λ_e·T_max and that \|Q_e\| is the close condition (`docs/paper-conformance.md` §3) |
| D7 | Exp. 1 at 5,000 req/s: load generator shares the c7i.4xlarge with VPS, committee and 7 Besu validators | pilot first; if client-bound notes appear, add a separate client instance (costs more) |

## 3. Before `deploy/aws/launch_run.sh experiment`

1. ~~Exp. 1 smoke completes locally~~ done.
2. `deploy/aws/launch_run.sh smoke` on the server: first real Besu + liboqs + STARK build there.
3. `deploy/aws/launch_run.sh pilot`: resolve D3, check CV for repetitions, saturation points, Exp. 5 gas.
4. Resolve D1–D8, then the experiment tier.

Nothing here is committed; the EC2 instance `i-0d832e0ca1fb0c9db` is stopped.
