# S13 — Zhang et al. [13], EAQ-VRBC

Paper: `Scheme/S13_Zhang2025_EAQ-VRBC/` · construction: `src/veredact_bench/methods/baselines/s13_eaq_vrbc/construction.py` ·
adapter: `adapter.py` (`EAQVRBCScheme`, key `S13`) · own evaluation: `reproduce.py` (Figs. 4–9).
The manuscript calls it "VRBC [13]".

## Role per experiment

| Exp | Enters | What S13 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request block-level redaction by the System Manager (Update phase) |
| 2 | ✗ | no per-request authorization protocol: authority = trapdoor possession (`auth_cost` = 0 operations). Excluded from `exp2.systems` rather than shown as a meaningless 0 ms bar |
| 3 | ✓ | Audit phase: challenge → aggregated tags + aggregated non-membership witness (Alg. 2, NI-SimPoE) |
| 4 | ✓ | AuditVerify (Alg. 3); **one decision for the whole challenged set** |
| 5 | ✓ | one `recordRedaction` transaction per redaction |

## Boundaries

- `authorize`: key-possession check only (the paper's model) — the Exp. 2 lower bound.
- `redact`: Redaction + Update (Sec. III-B): the Miner checks the current tag, the SM computes the
  double-trapdoor CH collision, the Auditee verifies the CH equation, a new identity-based tag is issued and
  checked, the old tag is revoked in the RSA accumulator; one ledger write.
- `audit`: challenge over the distinct blocks of the queried records; proof generation (service) and
  AuditVerify (auditor) timed separately. Tampering corrupts each affected block's tag once.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| RSA modulus | 2048 (112-bit) | 3072 (`rsa_bits`, 128-bit) in the comparison; 2048 in `reproduce.py` | against S13 (slower), required for equal security |
| audit witness timing | Alg. 1 per challenged block, every audit | every block's Alg. 1 witness built ONCE after the untimed history (one worker per physical core, each timed on one core; serial re-time if parallel timing is > 10 % inflated); an audit uses those exact witnesses: generation time = summed witness times + measured aggregation; bytes and verification measured directly (identical response: `test_fidelity.py`) | neutral (same work, single-core basis); per-sample spread narrower than a direct measurement |
| audit cost growth | Table III counts fixed-size Exp | Alg. 1's exponent b ≈ θ′ grows with the revocation history (≈ 6.9 s per witness at 10^4 redactions); the Auditee holds no φ(N) to reduce it | real property of Alg. 1 as written |
| primes | safe primes | standard RSA primes (equations unchanged) | for S13 (faster keygen, untimed) |
| H1 | odd l-bit values | same; non-coprime factors peeled (Alg. 1) | neutral |
| aggregation | recursive pairwise | balanced tree (same result, O(c log c) instead of O(c²)) | for S13 |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Query phase is reproduced in `reproduce.py` only (the comparison audits redaction records, not index queries).

## Fidelity checklist

- [x] rejects a nonexistent target
- [x] a tampered record makes the whole query fail (aggregate decision), no false accept
- [x] Alg. 2/3 verify for honest sets; non-membership fails for revoked tags (`tests/baselines/test_s13_eaq_vrbc.py`)
