# S34 — J. Xue et al. [34], REBS (attribute-based policy-hiding redaction)

Paper: `Scheme/S34_Xue2025_REBS/` · crypto: `experiment/S34_REBS/s34_scheme.py` ·
adapter: `s34_baseline.py` (`REBSScheme`, key `S34`) · own evaluation: `s34_run.py` (Figs. 3, 7).

## Role per experiment

| Exp | Enters | What S34 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request policy-gated redaction (Trap recovery + ChCld) |
| 2 | ✓ | authorization = LSSS policy decryption; committee axis = policy attributes l, t = ⌊2l/3⌋+1 |
| 3/4 | ✗ | "authorizable verification" means only AVN-authorised nodes verify attributes; there is no audit query → `NotSupported` |
| 5 | ✓ | one `recordRedaction` per redaction |

## Boundaries

- `authorize`: the TR decrypts `Info_Trap` with its attribute keys: one multi-pairing over 2t pairs plus a
  GT multi-exponentiation; succeeds only if its attribute VALUES satisfy the hidden policy (checked by
  `h_Trap`). A policy fault = TR whose keys were issued for another policy's values.
- `redact`: `ChCld` (d = e⁻¹ mod φ(n·ñ), r̃ = (h·H(Tx')^{−t})^d) → `ChVer` by the TR (ChCld step 4) →
  `ChVer` by the AVNs for consensus → one ledger write.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| group | composite order N = p1p2p3 (SS512, Charm) | prime-order BLS12-381 (dual-system → prime-order translation; every decryption equation kept) | for S34 (prime-order pairings are faster) |
| Trap encryption | Trap · e(g,g)^s in GT | Trap ⊕ KDF(e(g,g)^s) with `h_Trap` check (GT is not a message space for bytes) | neutral |
| RSA | 1024 | 3072 in the comparison (`rsa_bits`); 1024 in `s34_run.py` | against S34, required for equal security |
| AVNs | one per attribute (attribute i keyed by AVN_i's (ε_i, η_i), Lewko–Waters MA-ABE) | same: l attributes → l AVNs, so the AVN count is `policy_attributes`, not a separate parameter | none |
| AttrKeyGen | once per identity | at setup (and lazily, untimed, for identities first seen at run time) | for S34 (one-off Sig_AMC checks untimed) |
| CHash | per transaction at creation | materialised only for trace-targeted transactions (other transactions are never touched); ephemeral RSA keygen in a process pool | neutral (setup, untimed) |
| GT arithmetic | native exponentiation (PBC) | library exposes multiplication only → Straus multi-exponentiation in Python | against S34 (~5 ms of ~11 ms auth at t = 5) |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Delegate (AVN join/leave via re-encryption) — not exercised by any VeRedact experiment; Fig. 3(e) is
therefore not reproduced. Policy threshold is a (t, l) Vandermonde LSSS (the paper's threshold policies).

## Fidelity checklist (`s34_test.py`, `test_fidelity.py`)

- [x] authorised TR recovers Trap and redacts; ChVer holds on the new content, hash unchanged
- [x] t−1 attributes, or wrong attribute values → Trap not recovered
- [x] Sig_AMC bound to identity; keys of two TRs cannot be combined (collusion)
- [x] TimeUpdate keeps the hash; `audit` raises `NotSupported`
