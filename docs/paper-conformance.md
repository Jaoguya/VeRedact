# Paper conformance — manuscript vs. implementation

Where `overleaf/VeRedact.tex` (mirrored in `VeRedact.md`) and the code disagree. The code is not changed
to match the text where the text is wrong; the text must change. Line numbers refer to `overleaf/VeRedact.md`.

## 1. Baselines (decision taken: the four papers held in `Scheme/`)

| Where | Manuscript says | Implemented | Action |
|:--|:--|:--|:--|
| Sec. Evaluation intro (l. 1512) | primary baselines [14], [17], [27], [33]; audit baselines [13], [20] | S1 [1], S13 [13], S27 [27], S34 [34] | rewrite the baseline paragraph |
| Exp. 1 | Huang [14], Wang [17], Liu [27], Xue [33] | S1, S13, S27, S34 | rewrite |
| Exp. 2 (l. 1640) | Liu [27], Dong [15], Li [1] | S1, S27, S34 (S13 has no authorization protocol) | rewrite; say why S13 is absent |
| Exp. 3 (l. 1652) | VRBC [13], Xue [33], Miao [20] | S13, S1 (S27/S34 define no audit) | rewrite |
| Exp. 4 (l. 1664) | [13], [20], [33], "PQ-adapted and original classical" | S13, S1, original classical at 128-bit only | rewrite; see §3 |
| Exp. 5 | VeRedact-PQ vs Exp. 1 baselines | all five | wording only |
| Tables IV, V | rows for [14], [17], [27], [33] | — | replace with [1], [13], [27], [34] rows derived from the implementations |

## 2. Table I vs. the generated capability matrix (`make capabilities`)

| Row | Column | Table I | Code | Why |
|:--|:--|:-:|:-:|:--|
| [13] | Policy control | △ | ✗ | authority is trapdoor possession by the System Manager |
| [13] | Private verification | △ | ✗ | nothing is verified privately |
| [27] | Policy control | △ | ✗ | redactors approve content; no policy is evaluated |
| [27] | Scalable/batch | ✓ | ✗ | one Adapt + one ledger write per request (Sec. VI) |
| [27] | Verifiable auditing | △ | ✗ | no audit protocol |
| [34] | Distributed auth | △ | ✓ | t attribute keys from distinct AVNs are required (MA-ABE) |
| [34] | Verifiable auditing | ✓ | ✗ | "authorizable verification" = only authorised AVNs verify attributes; no audit query |
| [1] | Name | "Jia et al. [1]" | Li et al. [1] | ref [1] is Li et al. 2025 (Improved DCH on Jia's chain) |

## 3. Statements the evaluation cannot support as written

| Line | Statement | Status |
|:--|:--|:--|
| 1555 | "experiments … using identical PQ primitives across schemes" | **false as built**: baselines run their own classical primitives at 128-bit. A "PQ-adapted" RSA accumulator, CHET or pairing ABE is not defined by those papers and would be synthesised (rule 8). Decision needed — TASK.md D2 |
| Exp. 4 | "PQ-adapted and original classical instantiations" | only original classical implemented (same reason) |
| Phase 4 (l. 620) / Phase 5 (l. 746) | stale requests "returned for revalidation" | implemented as: the requester re-proves against the current state and resubmits. Because the PQZK statement binds `v_b`, revalidation **cannot** reuse the old proof — the text should say the requester re-proves |
| PQCH | "[TBD: confirm construction]" | SIS chameleon hash, MP12 gadget trapdoor, dealerless t-of-n; in distributed mode the perturbation is spherical, which leaks R statistically over many adaptations — must be fixed or stated (TASK.md D4) |
| Phase 4 (l. 576) | ABRRR B̂_e = f(λ_e, \|Q_e\|, T_max), f undefined | f = λ_e·T_max; \|Q_e\| enters as the close condition (\|Q_e\| ≥ B_e\*), not inside f — adding it to f would make size-based closing impossible. The text should define f |
| SA-RLI / RAI | Cuckoo filters CF_s per shard | exact membership sets (`ds/index.py`): no false positives, so a lookup never takes the filter-miss path a real Cuckoo filter would; negligible cost difference, state it or implement Cuckoo filters |
| PQZK | PrivatePolicy predicates | the STARK proves registry membership of the requester's credential + requester binding + statement binding; attribute predicates are **not** encoded (TASK.md D5) |
| Exp. 1 | rates up to 5,000 req/s | on one c7i.4xlarge the requester load generator shares the host; a client-bound point is recorded and stops the sweep (docs/experiments.md §4) |

## 4. Open manuscript issues (carried over)

| # | Issue | Where |
|:--|:--|:--|
| 1 | Stray `\section{Evaluation} skeleton in VedRedact.tex)` prints a duplicate heading | `VeRedact.tex` ~l. 2592 |
| 2 | ref [1] and ref [30] are the same paper | bibliography |
| 3 | "VRBC [13]" used as the name; ref [13] is EAQ-VRBC (Zhang et al.) | Table I, Sec. Evaluation |
| 4 | Every checkpoint carries a 3,309-B ML-DSA-65 signature; Exp. 5 will show VeRedact-PQ's per-redaction gas above hash-only baselines at small batches — the text must expect it | Exp. 5 |

## 5. Published numbers in the baseline papers (context only — never in our tables)

| Exp | Scheme | Reported by its authors |
|:--|:--|:--|
| 1 | S27 | end-to-end redaction < 0.38 s at 33 redactors, RTT 300 ms |
| 2 | S1 | Collision per party flat in t = 5…45; KeyGen quadratic |
| 3 | S13 | audit proof gen 0.040–0.478 s (c = 50…500) |
| 4 | S13 | audit verify 2.7–32.5 ms |
| 4 | S34 | ChVer ~3 ms, constant in l; Update 5.7 ms |
| 5 | S13 | Ropsten gas: redact 104,788; audit 158,336 |

`output.allow_published_numbers_in_tables = false`: every table number comes from this harness.
