# S13 — Zhang et al. [13], EAQ-VRBC

Paper: `Reference/S13_Zhang2025_EAQ-VRBC/` · construction: `Benchmark/src/veredact_bench/methods/baselines/s13_eaq_vrbc/construction.py` ·
adapter: `adapter.py` (`EAQVRBCScheme`, keys `S13`, `S13-per-block` and `S13-fallback`) · own evaluation: `reproduce.py` (Figs. 4–9).
The manuscript calls it "VRBC [13]".

## Role per experiment

| Exp | Enters | What S13 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request block-level redaction by the System Manager (Update phase) |
| 2 | ✗ | no per-request authorization protocol: authority = trapdoor possession (`auth_cost` = 0 operations). Excluded from `exp2.systems` rather than shown as a meaningless 0 ms bar |
| 3 | ✓ | Audit phase: challenge → aggregated tags + aggregated non-membership witness (Alg. 2, NI-SimPoE) |
| 4 | ✓ | `S13`: AuditVerify (Alg. 3), **one decision for the whole challenged set**. `S13-per-block` (#8): the paper's **Query** phase once per distinct block of the result, **one decision per block** — S13's finest output granularity, compared with VeRedact-PQ's per-record decisions. `S13-fallback` (#35): the Audit, and only if it returns F, the Query once per block; timed as both |
| 5 | ✗ | Exp. 5 measures VeRedact-PQ's own anchoring only; this scheme's per-redaction ledger write is part of its Exp. 1 |

## Boundaries

- `authorize`: key-possession check only (the paper's model) — the Exp. 2 lower bound.
- `redact`: Redaction + Update (Sec. III-B): the Miner checks the current tag, the SM computes the
  double-trapdoor CH collision, the Auditee verifies the CH equation, a new identity-based tag is issued and
  checked, the old tag is revoked in the RSA accumulator; one ledger write.
- `audit`: challenge over the distinct blocks of the queried records; proof generation (service) and
  AuditVerify (auditor) timed separately; the auditor takes the accumulator from the trusted node, as in the
  paper (not from the chain). Tampering corrupts each affected block's tag once.
- `audit` of `S13-per-block`: the paper's Query phase (Sec. III, "Query {(s, π_q) → T/F}") for every distinct
  block of the queried records: the Auditee returns (B_s, t_s, hh_s, w̄_x) with the same prebuilt Alg. 1
  witness as the Audit; the TPA checks non-membership (u^{aθ'} B^{∏s} = u), the identity-based tag and the
  chameleon hash `ch_s` — all three checks of the Query paragraph. A block's decision applies to each of its
  records. Runs on S13's own history (`HISTORY_OF`).

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| RSA modulus | 2048 (112-bit) | 3072 (`rsa_bits`, 128-bit) in the comparison; 2048 in `reproduce.py` | against S13 (slower), required for equal security |
| audit witness timing | Alg. 1 per challenged block, every audit | every block's Alg. 1 witness built ONCE after the untimed history, each timed alone, one after another (author 2026-11-01; the earlier parallel build inflated them 3–7 %); an audit uses those exact witnesses: generation time = summed witness times + measured aggregation; bytes and verification measured directly (identical response: `test_fidelity.py`) | neutral; per-sample spread narrower than a direct measurement |
| audit cost growth | Table III counts fixed-size Exp | Alg. 1's exponent b ≈ θ′ grows with the revocation history (median 67 s per witness at 10^5 redactions); the Auditee holds no φ(N) to reduce it | real property of Alg. 1 as written |
| primes | safe primes | standard RSA primes (equations unchanged) | for S13 (faster keygen, untimed) |
| H1 | odd l-bit values | same; non-coprime factors peeled (Alg. 1) | neutral |
| aggregation | recursive pairwise | balanced tree (same result, O(c log c) instead of O(c²)) | for S13 |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

The Query phase enters the comparison only as `S13-per-block` in Exp. 4 (per-block decisions); Exp. 3 uses the Audit.

## Fidelity checklist

- [x] rejects a nonexistent target
- [x] a tampered record makes the whole query fail (aggregate decision), no false accept
- [x] `S13-per-block`: a tampered record rejects exactly the records of its own block (`test_per_block_query_decides_each_block`)
- [x] `S13-fallback`: a clean query costs the Audit alone; a tampered one gets the per-block decisions, timed as Audit + Query (`test_fallback_runs_query_per_block_only_after_a_failed_audit`)
- [x] Alg. 2/3 verify for honest sets; non-membership fails for revoked tags (`Benchmark/tests/baselines/test_s13_eaq_vrbc.py`)
