# Paper conformance — manuscript vs. implementation

Where the final manuscript (`Overleaf/VeRedact-optimize.tex`) and the code differ. The code at `7d6c5b8` is accepted
as-is ("Peppo Implementation Strategy", author 2026-10-26): the gaps in §1 are not fixed; state them factually if
the results text or a reviewer touches them. The manuscript is edited only by the author.

## 1. Protocol gaps kept as they are (Peppo)

| # | Where | Manuscript | Code |
|:--|:--|:--|:--|
| 1 | Phase 6 transition node | checks PQCH.Hash for old and new (2 T_CH) | checks PQCH.Hash(MR_b', r_b') = CH_b only |
| 2 | Phase 6 routine request node | checks h_i^PQ = H(pi_i^PQ) | only in deep (escalated) mode |
| 3 | Phase 6 request node | recomputes L_i, L_i', checks Pi_i^SF | counts 2 T_H; tampering caught via h_PBRP |
| 4 | Audit response signature | H(enc(Body)) | H(Q, \|records\|, R_RAI, v_A) |
| 5 | Phase 3 | verifies the checkpoint signature sigma_b | not verified (the cost table also leaves it out) |
| 6 | Admission receipt rc_i | H(RID \|\| C_VR \|\| ts_adm) | H(RID \|\| H(R_i) \|\| ts) |
| 7 | Phase 3 signing | T_S in the cost table | 2 T_S (alpha_i and rc_i) |
| — | minor | RAI checkpoint uses e_A; CORA's f(·) and weights open | RAI checkpoint uses e; f = lambda_e · T_max; w_CH, w_F from Exp. 0 costs (`configs/methods/veredact.yaml`); the auditor rebuilds the RAI multiproof inside the timed step |

## 2. Text the author still has to write (results and setup)

| Where | Manuscript now | Code / run |
|:--|:--|:--|
| Setup, repetitions (l. 3057) | "three independent runs … 30 samples … mean over the three runs" for every experiment | Exp. 2–5: 3 runs × 10 samples per point (30 in total; S13 at n_Q = 10^4: 3 × 2), median = mean of per-run medians with a t CI (2 df), p95 pooled; Exp. 0 and 1: one run (Exp. 1: throughput CI over 6 × 10-s sub-windows, bootstrap p95 CI) |
| Setup, environment | "evaluated on a server" | each experiment on one AWS m7i.4xlarge (16 vCPU Xeon 8488C, 64 GiB, us-east-2); VeRedact-PQ's requesters prove on a separate c8g.48xlarge (Graviton4) — proof time equal to the server's (22.6 ms median) |
| Exp. 1 latency | "submission → finalized" | arrival → finalized; requests unfinished at the cutoff are censored (lower bound) |
| Exp. 5 | validators [TBD] | 4, 7, 10 |
| Baselines | four classical baselines | + S99 LETA (Li et al., IEEE JSAC 2026) in Exp. 0 and 2 (kept, author 2026-11-01): cite it and add its Table I row |
| S1 block size | — | one transaction per block (disclosed; `Other/docs/baselines/S1-improved-dch.md`) |
| S13 witness timing | — | each witness timed alone, one after another (author 2026-11-01); disclose that generation time = summed single-core witness times + measured aggregation |
| tab:primitives | [TBD] | filled from Exp. 0 (`make tables`) |

## 3. Table I vs. the generated capability matrix (`make capabilities`)

| Row | Column | Code | Why |
|:--|:--|:-:|:--|
| [13] | Policy control, Private verification | ✗ | authority is trapdoor possession by the System Manager; nothing is verified privately |
| [27] | Policy control, Scalable/batch, Verifiable auditing | ✗ | redactors approve content; one Adapt + one ledger write per request; no audit protocol |
| [34] | Distributed auth | ✓ | t attribute keys from distinct AVNs (MA-ABE) |
| [34] | Verifiable auditing | ✗ | "authorizable verification" = only authorised AVNs verify attributes; no audit query |

## 4. Published numbers in the baseline papers (context only — never in our tables)

| Exp | Scheme | Reported by its authors |
|:--|:--|:--|
| 1 | S27 | end-to-end redaction < 0.38 s at 33 redactors, RTT 300 ms |
| 2 | S1 | Collision per party flat in t = 5…45; KeyGen quadratic |
| 3 | S13 | audit proof gen 0.040–0.478 s (c = 50…500) |
| 4 | S13 | audit verify 2.7–32.5 ms |
| 4 | S34 | ChVer ~3 ms, constant in l; Update 5.7 ms |
| 5 | S13 | Ropsten gas: redact 104,788; audit 158,336 |

`output.allow_published_numbers_in_tables = false`: every table number comes from this harness.
