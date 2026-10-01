# S13 — Zhang et al. [13], EAQ-VRBC

Paper: `Scheme/S13_Zhang2025_EAQ-VRBC/` · crypto: `experiment/S13_EAQVRBC/s13_scheme.py` ·
adapter: `s13_baseline.py` (`EAQVRBCScheme`, key `S13`) · own evaluation: `s13_run.py` (Figs. 4–9).
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
- `redact`: revoke the old tag in the RSA accumulator, double-trapdoor CH collision for the block, new
  identity-based tag, one ledger write.
- `audit`: challenge over the distinct blocks of the queried records; proof generation (service) and
  AuditVerify (auditor) timed separately. Tampering corrupts each affected block's tag once.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| RSA modulus | 2048 (112-bit) | 3072 (`rsa_bits`, 128-bit) in the comparison; 2048 in `s13_run.py` | against S13 (slower), required for equal security |
| primes | safe primes | standard RSA primes (equations unchanged) | for S13 (faster keygen, untimed) |
| H1 | odd l-bit values | same; non-coprime factors peeled (Alg. 1) | neutral |
| aggregation | recursive pairwise | balanced tree (same result, O(c log c) instead of O(c²)) | for S13 |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Query phase is reproduced in `s13_run.py` only (the comparison audits redaction records, not index queries).

## Fidelity checklist

- [x] rejects a nonexistent target
- [x] a tampered record makes the whole query fail (aggregate decision), no false accept
- [x] Alg. 2/3 verify for honest sets; non-membership fails for revoked tags (`s13_test.py`)
