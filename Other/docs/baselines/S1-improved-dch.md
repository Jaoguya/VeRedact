# S1 — Li et al. [1], Improved DCH on Jia et al.'s redactable chain

Paper: `Reference/S1_Li2025_ImprovedDCH/` · construction: `Benchmark/src/veredact_bench/methods/baselines/s01_improved_dch/construction.py` ·
adapter: `adapter.py` (`ImprovedDCHScheme`, key `S1`) · own evaluation: `reproduce.py` (Table II, Fig. 2, attack).

## Role per experiment

| Exp | Enters | What S1 contributes |
|:--|:-:|:--|
| 1 | ✓ | per-request threshold redaction on Jia's chain (one redaction per block) |
| 2 | ✓ | t full nodes each check acc + verify tx/tx' signatures; committee axis = full nodes n, t = ⌊2n/3⌋+1; a batch of m = m independent authorizations |
| 3 | ✓ | consistency check (Jia Sec. III-C4): per queried block, block + RSA-accumulator membership witness |
| 4 | ✓ | client verifies Improved DCH + membership per record — per-record decisions; one level only |
| 5 | ✓ | one `recordRedaction` transaction per redaction; measured at every m (a batch of m = m transactions) |

## Boundaries

- `authorize`: the initiating node P and each of the t approving full nodes check locally that the block's
  header prime is not in the accumulated set (Sec. III-B3: "checks whether B has been redacted through the RSA
  accumulator acc"; a full node holds the set) and verify the ECDSA signatures of tx and tx'. tx' is signed by
  its creator before the timer. No non-membership witness is built per request: witnesses serve clients
  (consistency check, Sec. III-C4; audit A6), and building one per request cost O(history) — ~3 s per request
  at 3,500 redactions (audit A8).
- `redact`: threshold `Collision` over the new header content with t parties, `Verify`, accumulator
  update `acc ← acc^{H_prime(header')}`, one ledger write.
- `audit`: membership proofs `g^{∏ other primes}` held locally by the node (built once with RootFactor, audit
  A6); the client reads the anchored `acc` (header field, `recordRedactionWithAcc` / `latestAcc`) and each record
  (`getCommits`) from the chain, then checks Improved DCH and `wit^{H_prime(header)} = acc` per record.

## Instantiation and deviations

| Item | Paper | Here | Bias |
|:--|:--|:--|:--|
| pairing | PBC Type A/E/F (symmetric, < 128-bit) | BLS12-381, Type-3 translation (every equation keeps its form) | against S1 (larger, but equal-security) |
| accumulator | RSA, size unstated | RSA-3072 (`accumulator_rsa_bits`), hash-to-prime via `next_prime` | neutral at equal security |
| tx signatures | unspecified | ECDSA secp256k1 (coincurve) | neutral |
| one redaction per block | Jia's rule | enforced; a second request to a redacted block is rejected (reported, never retried) | real limit, not a harness artefact |
| block size | unstated | `txs_per_block` = 1 (10^6 blocks on the 10^6-transaction ledger; author decision 2026-10-18, disclosed in the manuscript) instead of the shared 256-transaction batch, so S1's audit history reaches n_Q = 10^5 without capping. History 2026-10-05: 8 transactions per block (12,500 blocks on 10^5 transactions, n_Q up to 10^4). The one-redaction-per-block rule is unchanged; with one transaction per block it means one redaction per transaction | for S1 (one-leaf Merkle root, fewer rejections of requests to an already-redacted block) |
| audit history | — | the shared untimed history list of every scheme (`data/history.py`) | neutral (setup, untimed) |
| chain setup | — | keys + chain (one Improved DCH hash per block, one owner signature per transaction) built once per process and reused by later points with the same ledger and parameters; each point redacts its own copy of the block headers (2026-10-18, like S34's hash table) | neutral (setup, untimed; ~11 min per build at 10^6 blocks) |
| membership proofs | "gets the membership proof locally or by running GenMem" (Sec. III-C4 step 2) | held locally: built once after the untimed history with RootFactor (all proofs in O(n log n); identical to GenMem, tested); an audit fetches them. Per-query GenMem would cost ~8 s per record at 10^4 redactions (22.6 h for one n_Q = 10^4 audit, measured) | for S1 (generation excludes GenMem), the paper's first option |
| ledger writes | one per redaction | one per redaction, **pipelined** (finality tracked, not awaited), exactly like VeRedact-PQ's anchoring | neutral — removes a harness-imposed one-block-per-redaction cap |

## Not implemented

Nothing S1 defines is omitted from the redaction/audit path. The collision attack on Jia's DCH is
reproduced separately (`reproduce.py`, `Benchmark/results/reproduction/S1/attack.csv`).

## Fidelity checklist (`Benchmark/tests/test_fidelity.py`, `Benchmark/tests/baselines/test_s01_improved_dch.py`)

- [x] rejects a nonexistent target; accepts policy/zk faults (no such checks in the paper)
- [x] exactly one redaction per touched block
- [x] tampered record rejected individually, valid records kept
- [x] Improved DCH collision verifies; Jia DCH forgeable, Improved DCH not (attack test)
