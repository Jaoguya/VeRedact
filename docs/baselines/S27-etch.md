# S27 — Liu et al. [27], ETCH (robust threshold redaction)

Paper: `Scheme/S27_Liu2026_ETCH/` · crypto: `experiment/S27_ETCH/s27_scheme.py` ·
adapter: `s27_baseline.py` (`ETCHScheme`, key `S27`) · own evaluation: `s27_run.py` (Figs. 4–6).

## Role per experiment

| Exp | Enters | What S27 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request threshold redaction (ETCH.Adapt, 2 CA rounds) |
| 2 | ✓ | t redactors verify the initiator's signature on h and sign approval; committee axis = redactors |
| 3/4 | ✗ | no audit protocol → `NotSupported` (nothing synthesised) |
| 5 | ✓ | one `recordRedaction` per redaction |

## Boundaries

- `authorize`: each of t redactors runs `verify_tx` (ETCH hash + ECDSA) and ECDSA-signs approval.
- `redact`: `redact_tx` (Adapt with t shares) → nodes re-verify → one ledger write.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| curve / hash | secp256k1 / SHA-256 | same (paper's own Sec. VII-B instantiation) | none |
| network | CA rounds over a network | in-process; `s27_run.py` Fig. 6 adds `adapt_rounds × RTT` for the paper's own figure only | for S27 in Exp. 1 (no RTT inside one host) |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Fig. 7 (chain growth) — the paper does not specify its update workload. KeyUpt is built and tested but
not on the redaction path.

## Fidelity checklist

- [x] rejects a nonexistent target; accepts policy/zk faults (no such checks in the paper)
- [x] `audit` raises `NotSupported`; `verifiable_auditing` capability is false
- [x] Adapt with t shares verifies; with t−1 it does not; KeyUpt keeps the hash key (`s27_test.py`)
