# S99 — Q. Li et al., LETA (lattice-based batch authentication with a per-vehicle ZKP)

paper: IEEE JSAC 44, 2026, doi 10.1109/JSAC.2025.3636982 · folder `Reference/S99_Li2026_LETA/` ·
code: `Benchmark/src/veredact_bench/methods/baselines/s99_leta/` — `construction.py` (Sec. IV),
adapter: `adapter.py` (`LETAScheme`, key `S99`) · own evaluation: `reproduce.py` (Table IV, Fig. 5).

The only post-quantum comparison scheme. It authenticates; it does not redact.

| Exp | Enters | What S99 contributes |
|---|---|---|
| 0 | yes | T_m (NTT product), Sign + ZKP (Eqs. 6-8), ZKP verify (Eqs. 14-15), aggregation of m0 signatures incl. VPD-Tree (Eqs. 9-12), aggregate verification (Eq. 13); m0 = `veredact.reference_batch` |
| 1 | no | no redaction |
| 2 | yes | per request: PL identity check (Sec. IV-B4c); per batch: VPD-Tree + aggregation (PL) + Eq. 13 (TEC), amortized / m like VeRedact-PQ Phase 4; no committee, flat in n |
| 3, 4 | no | no audit protocol (`NotSupported`) |
| 5 | no | no on-chain step defined by the comparison |

## Deviations (bias direction)

| Item | Paper | Here | Favours |
|---|---|---|---|
| parameters | none given (n, q, k, l, widths) | FIPS 204 ring n=256, q=8380417; rank 5 (ML-DSA-65's l); tau=49; gamma=2^19 (`configs/methods/s99_leta.yaml`) | neither (same level as VeRedact-PQ) |
| A | R_q^{k x l}, uses A^{-1} | square k x k (A^{-1} must exist), inverse once at setup, untimed | S99 (setup) |
| h1 | maps into a short ring element | its 32-byte SHAKE-256 seed (tree compares and re-hashes digests only) | S99 (slightly) |
| Sign | no rejection sampling | as written | S99 (no retries) |
| AggVerify | Eq. 13 only, c_i not recomputed | as written | S99 |
| language | Python on an M3 laptop | Python + NumPy (VeRedact-PQ's ML-DSA runs in liboqs C) | against S99 |
| signing in Exp. 2 | vehicle side | requester side, untimed (as VeRedact-PQ's sign + prove) | neither |

## Fidelity checklist (tests)

- NTT product equals the negacyclic schoolbook product; A A^{-1} = I (`tests/baselines/test_s99_leta.py`).
- Sign verifies; a changed message fails Eq. 15; a changed response fails Eq. 14.
- A valid platoon passes Eq. 13; one forged vehicle fails the whole batch; T - T5 > dT is refused.
- Adapter: absent target refused, redaction and audit raise `NotSupported` (`tests/test_fidelity.py`).
