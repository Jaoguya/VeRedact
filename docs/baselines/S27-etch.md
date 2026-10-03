# S27 — Liu et al. [27], ETCH (robust threshold redaction)

Paper: `Scheme/S27_Liu2026_ETCH/` · construction: `src/veredact_bench/methods/baselines/s27_etch/construction.py` ·
adapter: `adapter.py` (`ETCHScheme`, key `S27`) · own evaluation: `reproduce.py` (Figs. 4–6).

## Role per experiment

| Exp | Enters | What S27 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request threshold redaction (ETCH.Adapt, 2 CA rounds) |
| 2 | ✗ | no authorization step: redactors "reach a consensus" by unspecified means and the threshold is enforced only inside Adapt (`auth_cost` = 0 operations). Excluded from `exp2.systems`, like S13 |
| 3/4 | ✗ | no audit protocol → `NotSupported` (nothing synthesised) |
| 5 | ✓ | one `recordRedaction` per redaction |

## Boundaries

- `authorize`: target lookup only. No approval signatures — the paper defines none (an earlier version
  synthesised t ECDSA approvals; removed).
- `redact`: `redact_tx` (Adapt with t shares) → nodes re-verify → one ledger write.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| curve / hash | secp256k1 / SHA-256 | same (paper's own Sec. VII-B instantiation) | none |
| network | CA rounds over a network | in-process; `reproduce.py` Fig. 6 adds `adapt_rounds × RTT` for the paper's own figure only | for S27 in Exp. 1 (no RTT inside one host) |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Fig. 7 (chain growth) — the paper does not specify its update workload. KeyUpt is built and tested but
not on the redaction path.

## Fidelity checklist

- [x] rejects a nonexistent target; accepts policy/zk faults (no such checks in the paper)
- [x] `audit` raises `NotSupported`; `verifiable_auditing` capability is false
- [x] Adapt with t shares verifies; with t−1 it does not; KeyUpt keeps the hash key (`tests/baselines/test_s27_etch.py`)
