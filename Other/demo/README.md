# Live demo — one redaction, about 2 minutes

Every hash, signature and collision on screen is computed live by the project's own modules, loaded unchanged
from `Benchmark/src/veredact_bench/methods/veredact/`:

| On screen | Real code |
|---|---|
| D_i = H(m, ρ), L_i = H(I_i, D_i), h^PBRP | `crypto/hashing.py` (domain-separated SHA3-256), same formulas as `protocol/ledger.py` / `veredact.py` |
| Merkle root, proof of the old leaf, leaf update | `ds/merkle.py` |
| Block ID CH_b = PQCH(MR_b; r_b), 5-of-7 DKG, each member's share, combine | `crypto/pqch_sis.py` (n = 256, q = 2^16, as in `configs/base.yaml`) |
| owner's request signature, 5 committee approvals, checkpoint signature over H(r_b) | `crypto/pqsig.py`, ML-DSA-65 (pqcrypto backend) |
| the requester's private-policy proof (attribute ≥ 5, credential valid), ~31 KB | `crypto/pqzk_stark.py` + the Rust winterfell STARK in `native/pqzk_stark` (26 queries, blowup 32, as in `configs/base.yaml`) |

Needs Python 3 + `numpy` + `pqcrypto`, and for the ZK proof the Rust extension:

```bash
python -m pip install numpy pqcrypto
python -m pip install Benchmark/native/pqzk_stark      # needs Rust; on Windows the GNU toolchain is enough:
                                                       #   winget install Rustlang.Rustup
                                                       #   rustup default stable-x86_64-pc-windows-gnu
```

Without the extension the demo still runs and the ZK step says "skipped". No AWS, no Besu.

```bash
python Other/demo/server.py
```

then open **http://localhost:8765**. The first start runs the committee key generation (~15 s) and caches it
in `Other/demo/.cache/`; after that it starts instantly. **Start it once before class** so the cache exists.

## The script (≈ 2 min)

| # | Do | Say |
|---|---|---|
| 1 | Point at the chain strip on top | "Block #17's ID is a **chameleon hash** of its transactions — a lattice hash, safe against quantum computers. Block #18 points to that ID." |
| 2 | Point at tx 2 (orange *personal data*) | "Row 2 holds a phone number and a national ID. Under PDPA/GDPR the owner can ask us to erase it — a normal blockchain can't, without breaking every later block." |
| 2b | **Attribute too low** → Redact, then **Replays an old proof** → Redact, then back to **Valid ✓** | "Before any committee: the requester proves in zero knowledge that their *hidden* attribute meets the policy. Too low: no proof can even be built. A stolen proof from another request: rejected, because it is bound to that request. Valid: a 31 KB STARK, checked in half a millisecond — and the VPS never learns the attribute (blurred side)." |
| 3 | **only 4** → **Redact with committee** | "7 members, each holding only a *share* of the secret trapdoor. With 4: rejected, nothing written." |
| 4 | **5 approve** → **Redact with committee** | Keys light up. Watch the table fill: "content, commitment, leaf, Merkle root, randomness — **all changed**. Block ID: 🔒 **same**. The new randomness absorbs the change, so #18 still links." |
| 5 | **Attacker edit** | Block #17 shakes, the link to #18 breaks: "No trapdoor, so the randomness can't be adapted — the ID changes and everyone sees it. Forging it means solving SIS, which quantum computers don't break." |
| 6 | Open **Details** (only if asked) | Every check that ran (ML-DSA signatures, leaf proof, 5 shares), per-member timings, and the audit record. |

Close with the footer: the AWS-measured numbers from release `run-2026-11-12`.

## What the demo leaves out (say it if asked)

One block of 8 transactions. Not here: the SA-RLI/RAI indexes, CORA/SFMR batching across many blocks, BatchAttest and RoundCheckpoint
(the demo signs per request and per checkpoint, the pre-optimisation form), the Besu chain and SAVER auditing.
With 4 approvals the real system stops at Phase 4; the demo still runs the 4-share adaptation once, only to
show that it gives no valid collision. Timings on screen are this laptop; the paper's numbers are AWS.

## Likely questions

- **"Isn't a redactable blockchain just a mutable database?"** No: only a 5-of-7 committee can redact, every
  redaction is recorded and auditable, and anyone else's edit is detected immediately.
- **"Why post-quantum?"** The classical schemes we compare against (RSA, pairings, ECDSA) fall to Shor's
  algorithm; a ledger is meant to last decades.
- **"What does it cost?"** On AWS, one member's share of a redaction is 15.1 ms and the lattice hash 1.07 ms;
  batching (CORA/SFMR) shares that cost across every request in a round.

## If something breaks in class

- Port busy: `python Other/demo/server.py 8766` and open that port.
- `ModuleNotFoundError`: `python -m pip install numpy pqcrypto`.
- Start over at any time with **Reset** (new random r, same committee).
