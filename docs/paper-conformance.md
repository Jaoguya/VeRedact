# Paper conformance — manuscript vs. implementation

Where the manuscript (`overleaf/VeRedact-2.tex`, mirrored in `VeRedact.md`) and the code disagree. The
manuscript is final (2026-10-03): the code follows it wherever it is right, and every text change it still
needs is in `overleaf/newchange.md` with line numbers. Line numbers below refer to the older `VeRedact.md`.

## 1. Baselines (decision taken: the four papers held in `Scheme/`) — applied to the .tex 2026-10-01

| Where | Manuscript says | Implemented | Action |
|:--|:--|:--|:--|
| Sec. Evaluation intro (l. 1512) | primary baselines [14], [17], [27], [33]; audit baselines [13], [20] | S1 [1], S13 [13], S27 [27], S34 [34] | rewrite the baseline paragraph |
| Exp. 1 | Huang [14], Wang [17], Liu [27], Xue [33] | S1, S13, S27, S34 | rewrite |
| Exp. 2 (l. 1640) | Liu [27], Dong [15], Li [1] | S1, S34 (S13: key possession; S27: threshold only inside Adapt, no approval step) | rewrite; say why S13 and S27 are absent |
| Exp. 3 (l. 1652) | VRBC [13], Xue [33], Miao [20] | S13, S1 (S27/S34 define no audit) | rewrite |
| Exp. 4 (l. 1664) | [13], [20], [33], "PQ-adapted and original classical" | S13, S1, original classical at 128-bit only | rewrite; see §3 |
| Exp. 5 | VeRedact-PQ vs Exp. 1 baselines | all five | wording only |
| Tables IV, V | rows for [14], [17], [27], [33] | — | replaced with [1], [13], [27], [34] rows derived from the papers (row comments cite the sections) |

## 2. Table I vs. the generated capability matrix (`make capabilities`) — applied to the .tex 2026-10-01

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
| 1555 | "experiments … using identical PQ primitives across schemes" | **fixed 2026-10-01** (text now: own classical primitives at ~128-bit). Was **false as built**: baselines run their own classical primitives at 128-bit. A "PQ-adapted" RSA accumulator, CHET or pairing ABE is not defined by those papers and would be synthesised (rule 8). Decision needed — TASK.md D2 |
| Exp. 4 | "PQ-adapted and original classical instantiations" | **fixed 2026-10-01**: text now says original classical only |
| Phase 4 (l. 620) / Phase 5 (l. 746) | stale requests "returned for revalidation" | implemented as: the requester re-proves against the current state and resubmits. Because the PQZK statement binds `v_b`, revalidation **cannot** reuse the old proof — the text should say the requester re-proves |
| PQCH | "[TBD: confirm construction]" | SIS chameleon hash, MP12 gadget trapdoor, dealerless t-of-n — fill text in `newchange.md` B3; in distributed mode the perturbation is spherical, which leaks R statistically over many adaptations — must be fixed or stated (TASK.md D4) |
| Phase 4 (l. 576) | ABRRR B̂_e = f(λ_e, \|Q_e\|, T_max), f undefined | f = λ_e·T_max; \|Q_e\| enters as the close condition (\|Q_e\| ≥ B_e\*), not inside f — adding it to f would make size-based closing impossible. Text fix: `newchange.md` A4 |
| SA-RLI / RAI | Cuckoo filters CF_s per shard | **implemented 2026-10-03** (`ds/cuckoo.py`): 16-bit fingerprints, synchronized with the finalized snapshot; positives and unsynchronized negatives take the authenticated lookup |
| PQZK | PrivatePolicy predicates | **implemented 2026-10-03**: attribute ≥ policy threshold and expiry > ts_r proven as 32-bit range proofs in the AIR, besides membership + requester + statement binding |
| Phases 3–6 | admission receipt rc_i, C_VR reconstruction, Auth_e^B check before execution, BIMC multiproof check, auditor-signed queries | **implemented 2026-10-03**; the extra rc_i signature and Auth check are not in Table IV — `newchange.md` A1–A3 |
| Exp. 1 | rates up to 5,000 req/s | on one c7i.4xlarge the requester load generator shares the host; a client-bound point is recorded and stops the sweep (docs/experiments.md §4) |

## 4. Open manuscript issues (carried over)

| # | Issue | Where |
|:--|:--|:--|
| 1 | ~~Stray `\section{Evaluation} skeleton` heading~~ now a comment in `VeRedact-2.tex` | — |
| 2 | ref [1] and ref [30] are the same paper | bibliography — `newchange.md` A6 |
| 3 | ~~"VRBC [13]" used as the name~~ fixed 2026-10-01: now "Zhang et al. [13]" | Table I, Sec. Evaluation |
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
