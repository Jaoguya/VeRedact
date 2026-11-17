# Live demo — the whole VeRedact-PQ protocol, Phase 1 to 6

Not a mock-up and not a re-implementation: `server.py` opens the real system exactly as the tests and the
benchmark do (`open_system(cfg, "veredact", ds)`, smoke tier) and calls its phases one at a time. Every hash,
signature, proof, collision and audit decision on screen is produced by `Benchmark/src/veredact_bench/`.

| Phase | Entities (system model) | Real code that runs |
|---|---|---|
| 1 Setup | all | `Ledger.__init__`: ML-DSA-65 keys, dealerless 5-of-7 PQCH DKG, policies C_P, STARK credential registry |
| 2 Commit | Data Owner → PBN | `commit_transactions`: D = H(m‖ρ) signed by the owner, I, L = H(I‖D), Merkle trees, CH_b, SA-RLI, signed checkpoints |
| 3 Request | Requester → VPS | `prepare` (ML-DSA-65 + PQZK STARK proof) and `authorize` → `validate`: SA-RLI, signature, policy, FreshLeaf, PQZK, BatchAttest |
| 4 Authorize | VPS → Committee → PBN | `select_round` (CORA) + `authorize_batch`: t ML-DSA approvals on C_B, R_VR, Γ, anchored |
| 5 Execute | Committee → PBN | `redact`: SFMR, distributed PQCH adaptation (one per batch), RoundCheckpoint, finalization anchored |
| 6 Audit | PBN (audit service) → Auditor | `index_records` (RAI + CP_A) and `audit`: signed query, response, SAVER per-record verification |

Attacks are the system's own fault injection — the request faults of Exp. 1 (`sig`, `zk`, `policy`, `stale`,
`replay`, `absent`) and the audit tampering of Exp. 4 (`modified`, `substituted`, `stale`, `forged_approval`,
`forged_proof`) — plus, in Phase 5, 4 of 7 members using their real trapdoor shares, and an outsider editing a
record without them.

## Run

```bash
bash Other/demo/chain.sh up                           # 1. a REAL chain: 4 Besu QBFT validators in Docker
                                                      #    (Docker Desktop running; first time pulls the image)
python -m pip install numpy omegaconf pqcrypto cryptography "web3==8.0.0" "py-solc-x==2.0.5"
python -m pip install Benchmark/native/pqzk_stark     # the STARK; needs Rust. On Windows the GNU toolchain works:
                                                      #   winget install Rustlang.Rustup
                                                      #   rustup default stable-x86_64-pc-windows-gnu
python Other/demo/server.py                           # 2. then open http://localhost:8765
```

With the chain running, the server uses the project's own Besu backend (`evaluation/anchor.py`): it compiles and
deploys `contracts/VeRedactRegistry.sol`, and every anchoring step is a real transaction mined in QBFT blocks
(2 s period); each phase shows its receipts (time to mine, gas). Without the chain it falls back to the
in-process ledger and says so on the page. Stop the chain afterwards with `bash Other/demo/chain.sh down`.

Setup (Phases 1–2) takes ~45 s on the chain (~30 s without) at start and on **Reset system**. **Start it before class.**

- Wait for `demo on http://localhost:8765`, then open that address in any browser (Chrome, Edge). F11 = full screen.
- **Keep the server window open** while presenting; closing it stops the demo.
- `localhost` only works on the machine running the server: run it on the laptop connected to the projector.
- Several Pythons installed? Use the one you installed the packages into, by full path, e.g.
  `& "C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe" Other/demo/server.py` (PowerShell).

## The script (≈ 3 min — one click per phase)

| Click | Point at | Say |
|---|---|---|
| **Phase 1** | everything lights up, then the PBN bar | "This is a real blockchain: four Besu validators running QBFT consensus — watch the block number climb — with our smart contract deployed. Six roles from our system model. Everyone gets post-quantum keys; the committee creates the redaction trapdoor *in shares* — nobody ever holds it whole." |
| **Phase 2** | the 16 batch chips | "4,096 transactions in 16 batches. Each batch's ID is a lattice chameleon hash. Our record, batch 3, holds a phone number and a national ID." |
| **Phase 3**, set *who is asking* to **no valid credential** | the VPS checklist | "An attacker without a valid credential: the zero-knowledge check fails, the committee never sees it." Switch back to **Honest owner**, **Run this phase again**: "The owner proves in ~15 ms, with a ~29 KB STARK, that a *hidden* attribute meets the policy. The VPS learns yes or no, never the attribute." |
| **Phase 4** | the 7 member boxes | "CORA picks the round — 4 requests in 3 batches. Five of seven members sign it." |
| **Phase 5** | batch table + chips | "Merkle root changed, randomness changed, **batch ID the same** — for all three batches. Four redactions, only **three** chameleon-hash adaptations: two requests in batch 3 shared one. That sharing is SFMR." Then **⚔ Attack this phase**: "Four members alone, or an outsider: no valid collision, the ID would change." |
| **Phase 6**, set *auditor gets* to **Evidence of another redaction swapped in** | the audit table | "The auditor rejects exactly the forged record and keeps the others — it can say *which* one. Authorization evidence was checked once for all four records: that is SAVER." Try **Forged committee approval**: all four fail, because they share that approval. |

## What is smaller than the paper (say it if asked)

Smoke tier sizes: 4,096 transactions instead of 10^5, a 128-slot credential registry instead of 2^15, and a
4-validator Besu QBFT chain on the laptop instead of the benchmark's 7 validators with 10 ms netem links. The security parameters are the paper's:
ML-DSA-65, STARK with 26 queries / blowup 32, PQCH n = 256, q = 2^16, 5-of-7 committee. Timings on screen are
this laptop; the paper's numbers come from AWS (footer: release `run-2026-11-12`).

## If something breaks in class

- Port busy: `python Other/demo/server.py 8766`.
- `ModuleNotFoundError`: re-run the two `pip install` lines.
- Any phase can be re-run from the step bar; **Reset system** rebuilds everything (~10–30 s).
