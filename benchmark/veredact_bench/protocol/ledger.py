"""VeRedact-PQ Phase 1 (setup) and Phase 2 (redaction-aware transaction commitment).

Materialises the shared dataset into VeRedact-PQ's native form: RADC commitments (I_i, D_i), Merkle
transaction batches under a distributed SIS chameleon hash, SA-RLI, signed checkpoints anchored on the
ledger backend. Runs inside Scheme.setup() — NOT timed.
"""
import os
import time
from dataclasses import dataclass

from ..crypto import Crypto
from ..ds.index import rai, sa_rli
from ..ds.merkle import MerkleTree
from .types import Checkpoint, Tx


@dataclass
class Batch:
    b: int
    tids: list
    tree: MerkleTree
    ch: bytes
    r: object
    v: int = 0


@dataclass
class Policy:
    PID: str
    body: str
    v: int
    e_P: int
    C_P: bytes
    ops: tuple = ("modify", "delete")


class Ledger:
    def __init__(self, cfg: dict, crypto: Crypto, anchor, committee_n: int, committee_t: int):
        v, d = cfg["veredact"], cfg["dataset"]
        self.cfg, self.c, self.anchor = cfg, crypto, anchor
        self.n, self.t, self.N = committee_n, committee_t, d["leaves_per_batch"]
        self.e = 1  # authorization epoch
        # ---- Phase 1 Step 2: entity keys (ML-DSA-65); Step 1: 2*lambda-bit PRF keys ----------------------
        kb = cfg["security"]["prf_key_bits"] // 8
        self.K_idx, self.K_A = os.urandom(kb), os.urandom(kb)
        self.vps, self.cp, self.audit_svc, self.auditor = (crypto.keygen() for _ in range(4))
        self.requesters = [crypto.keygen() for _ in range(d["requesters"])]
        self.committee = [crypto.keygen() for _ in range(committee_n)]
        # ---- Step 3: policies bind the STARK credential registry root (C_P) ------------------------------
        root = crypto.zk.root
        self.policies = {}
        for j in range(d["policies"]):
            pid, body = f"P{j}", f"registry={root[0]:x}{root[1]:x}; ops=modify|delete"
            self.policies[pid] = Policy(pid, body, 1, 0, crypto.H(pid, body, 1, 0))
        # ---- Step 4-5: committee + dealerless PQCH DKG ---------------------------------------------------
        self.pk_ch, self.td = crypto.ch.dkeygen(committee_n, committee_t)
        self.pending_setup = [anchor.submit("policy_register", pid=crypto.H(p.PID), commit=p.C_P)
                              for p in self.policies.values()]
        self.pending_setup.append(anchor.submit("committee_register", epoch=self.e,
                                                members=crypto.H(*[k.pk for k in self.committee]),
                                                n=committee_n, t=committee_t))
        # ---- Phase 2 state -------------------------------------------------------------------------------
        self.txs: dict[bytes, Tx] = {}
        self.batches: dict[int, Batch] = {}
        self.checkpoints: dict[int, Checkpoint] = {}
        self.rli = sa_rli(v["rli_shards"])
        self.rai = rai(v["rai_shards"])
        self.used_nonces: set = set()

    # ------------------------------------------------------------------ Phase 2
    def commit_transactions(self, transactions: list):
        c = self.c
        pids = list(self.policies)
        for off in range(0, len(transactions), self.N):
            b = len(self.batches)
            tids = []
            for pos, src in enumerate(transactions[off:off + self.N]):
                tx = Tx(TID=src.tid, m=src.payload, rho=os.urandom(32), DT="record",
                        PID=pids[src.policy % len(pids)], ts=src.ts, owner=src.owner)
                tx.D = c.H(tx.m, tx.rho)  # salted content commitment D_i
                tx.Tag = c.H(tx.TID, os.urandom(16), tx.ts)
                tx.I = c.H(tx.TID, tx.owner, tx.DT, tx.PID, tx.ts, tx.Tag)
                tx.b, tx.pos, tx.e_i = b, pos, self.e
                self.txs[tx.TID] = tx
                tids.append(tx.TID)
            tree = MerkleTree([c.H(self.txs[t].I, self.txs[t].D) for t in tids])
            r = c.ch.sample_r()
            self.batches[b] = Batch(b, tids, tree, c.ch_hash(self.pk_ch, tree.root, r), r)
            for tid in tids:
                self._index_put(self.txs[tid])
        R = self.rli.finalize()
        for b in range(len(self.batches)):
            if b not in self.checkpoints:
                self.checkpoints[b] = cp = self._checkpoint(b, R)
                self.pending_setup.append(self.anchor.submit("batch_checkpoint", b=b, mr=cp.MR, rli=R, sig=cp.sigma))
        for f in self.pending_setup:  # setup finishes only when everything is on the ledger
            f.result()
        self.pending_setup = []

    def _index_put(self, tx: Tx):
        tau = self.c.PRF(self.K_idx, tx.TID)
        self.rli.put(tau, self.c.H(tau, tx.Tag, tx.b, tx.pos, tx.PID, tx.e_i, tx.I, tx.D))

    def _checkpoint(self, b: int, R_RLI: bytes) -> Checkpoint:
        bt = self.batches[b]
        ts = int(time.time())
        msg = self.c.H(b, bt.ch, bt.tree.root, bt.r.tobytes(), R_RLI, self.rli.snapshot, self.e, bt.v, ts)
        return Checkpoint(b, bt.ch, bt.tree.root, bt.r.copy(), R_RLI, self.rli.snapshot, self.e, bt.v, ts,
                          self.c.sign(self.cp.sk, msg))
