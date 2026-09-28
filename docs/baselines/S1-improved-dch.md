# S1 — Li et al. [1], Improved DCH on Jia et al.'s redactable chain

Paper: `Scheme/S1_Li2025_ImprovedDCH/` · crypto: `experiment/S1_ImprovedDCH/s1_scheme.py` ·
adapter: `s1_baseline.py` (`ImprovedDCHScheme`, key `S1`) · own evaluation: `s1_run.py` (Table II, Fig. 2, attack).

## Role per experiment

| Exp | Enters | What S1 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request threshold redaction on Jia's chain (one redaction per block) |
| 2 | ✓ | t full nodes each check acc + verify tx/tx' signatures; committee axis = full nodes n, t = ⌊2n/3⌋+1 |
| 3 | ✓ | consistency check (Jia Sec. III-C4): per queried block, block + RSA-accumulator membership witness |
| 4 | ✓ | client verifies Improved DCH + membership per record — per-record decisions; one level only |
| 5 | ✓ | one `recordRedaction` transaction per redaction |

## Boundaries

- `authorize`: t approving nodes, each (a) checks via the accumulator that the block was not redacted
  before, (b) verifies the ECDSA signatures of tx and tx'. tx' is signed by its creator before the timer.
- `redact`: threshold `Collision` over the new header content with t parties, `Verify`, accumulator
  update `acc ← acc^{H_prime(header')}`, one ledger write.
- `audit`: witness `g^{∏ other primes}` built by the service; the client checks Improved DCH and
  `wit^{H_prime(header)} = acc` per record.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| pairing | PBC Type A/E/F (symmetric, < 128-bit) | BLS12-381, Type-3 translation (every equation keeps its form) | against S1 (larger, but equal-security) |
| accumulator | RSA, size unstated | RSA-3072 (`accumulator_rsa_bits`), hash-to-prime via `next_prime` | neutral at equal security |
| tx signatures | unspecified | ECDSA secp256k1 (coincurve) | neutral |
| one redaction per block | Jia's rule | enforced; a second request to a redacted block is rejected (reported, never retried) | real limit, not a harness artefact |

## Not implemented

Nothing S1 defines is omitted from the redaction/audit path. The collision attack on Jia's DCH is
reproduced separately (`s1_run.py`, `S1_attack.csv`).

## Fidelity checklist (`benchmark/tests/test_fidelity.py`, `experiment/S1_ImprovedDCH/s1_test.py`)

- [x] rejects a nonexistent target; accepts policy/zk faults (no such checks in the paper)
- [x] exactly one redaction per touched block
- [x] tampered record rejected individually, valid records kept
- [x] Improved DCH collision verifies; Jia DCH forgeable, Improved DCH not (attack test)
