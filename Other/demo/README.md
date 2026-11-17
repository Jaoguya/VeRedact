# Live demo — one redaction, about 2 minutes

Every hash, signature and collision on screen is computed live by the project's own modules, loaded unchanged
from `Benchmark/src/veredact_bench/methods/veredact/`:

| On screen | Real code |
|---|---|
| D_i = H(m, ρ), L_i = H(I_i, D_i), h^PBRP | `crypto/hashing.py` (domain-separated SHA3-256), same formulas as `protocol/ledger.py` / `veredact.py` |
| Merkle root, proof of the old leaf, leaf update | `ds/merkle.py` |
| Block ID CH_b = PQCH(MR_b; r_b), 5-of-7 DKG, each member's share, combine | `crypto/pqch_sis.py` (n = 256, q = 2^16, as in `configs/base.yaml`) |
| owner's request signature, 5 committee approvals, checkpoint signature over H(r_b) | `crypto/pqsig.py`, ML-DSA-65 (pqcrypto backend) |

Needs Python 3 + `numpy` + `pqcrypto` (`python -m pip install numpy pqcrypto`). No AWS, no Besu, no Rust.

```bash
python Other/demo/server.py
```

then open **http://localhost:8765**. The first start runs the committee key generation (~15 s) and caches it
in `Other/demo/.cache/`; after that it starts instantly. **Start it once before class** so the cache exists.

## The script (≈ 2 min)

| # | Do | Say |
|---|---|---|
| 1 | Point at the left card | "This is one block. Its ID is a **chameleon hash** of the transactions — a lattice hash, 1 KB, safe against quantum computers. The next block points to this ID." |
| 2 | Point at tx 2 (orange *personal data*) | "Row 2 holds a phone number and a national ID. Under PDPA/GDPR the owner can ask us to erase it — but a normal blockchain can't change anything without breaking every later block." |
| 3 | Click **only 4 approve** → **Redact** | "Our committee has 7 members, each holding only a *share* of the secret trapdoor. With 4, the approval check fails and **nothing is written** — and the screen shows that even forced, 4 shares give no valid collision: the ID would change." |
| 4 | Click **5 approve** → **Redact** | "With 5 of 7 it goes through." Point at table 3: "content, commitment D, leaf, Merkle root, randomness r — **every hash changed**. The block ID: **same**. The new r absorbs the change, so the chain stays linked." Point at table 4: "each check is real: ML-DSA signatures, the leaf proof, ~11 ms per member's share." |
| 5 | Click **Attacker: edit without trapdoor** | "An attacker without the trapdoor edits the same block: the ID changes, the link breaks, everyone sees it. Finding a collision without the trapdoor means solving SIS, a lattice problem quantum computers don't break." |
| 6 | Point at **Audit record** | "Every redaction leaves a record — old and new commitment D, version, who approved, and its PBRP digest — so an auditor can check later that it was authorized." |

Close with the footer: the AWS-measured numbers from release `run-2026-11-12`.

## What the demo leaves out (say it if asked)

One block of 8 transactions. Not here: the STARK proof that the requester satisfies the policy without
revealing it, the SA-RLI/RAI indexes, CORA/SFMR batching across many blocks, BatchAttest and RoundCheckpoint
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
