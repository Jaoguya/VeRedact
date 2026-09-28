"""Shared ledger substrate: Phase 1 setup + Phase 2 transaction commitment (RADC, Merkle/PQCH batches, SA-RLI).

Both VeRedact-PQ and the re-implemented baselines run on this substrate so that differences come
from the redaction workflow, not from the ledger model ("identical PQ primitives across schemes").
"""
import os
import time
from dataclasses import dataclass, field

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


@dataclass
class ChainLog:
    """On-chain operations (for Exp. 5 gas modelling and the Besu contract replay)."""
    ops: list = field(default_factory=list)

    def anchor(self, op: str, payload_bytes: int, **meta):
        self.ops.append({"op": op, "bytes": payload_bytes, **meta})


class Ledger:
    def __init__(self, crypto: Crypto, n=7, t=5, N=256, S=16, S_A=16, n_owners=8, n_requesters=16,
                 n_policies=4, sign_transactions=False):
        self.c = crypto
        self.n, self.t, self.N = n, t, N
        self.e = 1  # authorization epoch
        self.chain = ChainLog()
        self.sign_transactions = sign_transactions
        # ---- Phase 1: setup -----------------------------------------------------
        self.K_idx, self.K_A = os.urandom(32), os.urandom(32)  # 2*lambda-bit PRF keys
        self.vps = crypto.keygen()
        self.cp = crypto.keygen()  # checkpoint authority (PBN ordering service)
        self.audit_svc = crypto.keygen()
        self.owners = [crypto.keygen() for _ in range(n_owners)]
        self.requesters = [crypto.keygen() for _ in range(n_requesters)]
        self.auditor = crypto.keygen()
        self.committee = [crypto.keygen() for _ in range(n)]
        self.policies = {}
        for j in range(n_policies):
            pid, body = f"P{j}", f"role in {{R{j}}}; ops modify|delete; valid e<=100"
            C_P = crypto.H(pid, body, 1, 0)
            self.policies[pid] = Policy(pid, body, 1, 0, C_P)
            self.chain.anchor("policy_register", 32 + 3 * 16, phase=1)
        self.chain.anchor("committee_register", 16 + n * 32 + 16, phase=1)
        self.pk_ch, self.td, self.T_full = crypto.ch.dkeygen(n, t)
        self.zk_params = crypto.zk.setup("R_P")
        # ---- Phase 2 state --------------------------------------------------------
        self.txs: dict[bytes, Tx] = {}
        self.batches: dict[int, Batch] = {}
        self.checkpoints: dict[int, Checkpoint] = {}
        self.rli = sa_rli(S)
        self.rai = rai(S_A)
        self.used_nonces: set = set()

    def clone(self) -> "Ledger":
        """Independent copy of all mutable ledger state; crypto backends and keys are shared."""
        import copy

        shared = [self.c, self.pk_ch, self.T_full, self.zk_params, self.vps, self.cp, self.audit_svc,
                  self.auditor, *self.owners, *self.requesters, *self.committee, *self.td.values()]
        return copy.deepcopy(self, {id(o): o for o in shared})

    # ------------------------------------------------------------------ Phase 2
    def commit_transactions(self, payloads: list[bytes], owners=None, policies=None):
        """Commit payloads in batches of N leaves (RADC + Merkle + PQCH + SA-RLI + checkpoint)."""
        c = self.c
        pids = list(self.policies)
        start = len(self.txs)
        for off in range(0, len(payloads), self.N):
            chunk = payloads[off:off + self.N]
            b = len(self.batches)
            tids = []
            for k, m in enumerate(chunk):
                i = start + off + k
                owner = owners[i] if owners else i % len(self.owners)
                pid = policies[i] if policies else pids[i % len(pids)]
                tx = Tx(TID=f"TX{i}".encode(), m=m, rho=os.urandom(32), DT="record", PID=pid,
                        ts=int(time.time()), owner=owner)
                tx.D = c.H(tx.m, tx.rho)  # salted content commitment
                if self.sign_transactions:
                    tx.sigma = c.sign(self.owners[owner].sk, c.H(tx.TID, tx.D, tx.DT, tx.PID, tx.ts))
                tx.Tag = c.H(tx.TID, os.urandom(16), tx.ts)
                tx.I = c.H(tx.TID, owner, tx.DT, tx.PID, tx.ts, tx.Tag)
                tx.b, tx.pos, tx.e_i = b, k, self.e
                self.txs[tx.TID] = tx
                tids.append(tx.TID)
            tree = MerkleTree([c.H(self.txs[t].I, self.txs[t].D) for t in tids])
            r = c.ch.sample_r()
            ch = c.ch_hash(self.pk_ch, tree.root, r)
            self.batches[b] = Batch(b, tids, tree, ch, r)
            for tid in tids:
                self._index_put(self.txs[tid])
        R = self.rli.finalize()
        for b in range(len(self.batches)):
            if b not in self.checkpoints:
                self.checkpoints[b] = self._checkpoint(b, R)
                self.chain.anchor("batch_checkpoint", self.checkpoint_bytes(), phase=2, b=b)

    def leaf(self, tx: Tx, D=None) -> bytes:
        return self.c.H(tx.I, tx.D if D is None else D)

    def _index_put(self, tx: Tx):
        tau = self.c.PRF(self.K_idx, tx.TID)
        entry = self.c.H(tau, tx.Tag, tx.b, tx.pos, tx.PID, tx.e_i, tx.I, tx.D)
        self.rli.put(tau, entry)

    def _checkpoint(self, b: int, R_RLI: bytes) -> Checkpoint:
        bt = self.batches[b]
        ts = int(time.time())
        msg = self.c.H(b, bt.ch, bt.tree.root, bt.r.tobytes(), R_RLI, self.rli.snapshot, self.e, bt.v, ts)
        sig = self.c.sign(self.cp.sk, msg)
        return Checkpoint(b, bt.ch, bt.tree.root, bt.r.copy(), R_RLI, self.rli.snapshot, self.e, bt.v, ts, sig)

    def checkpoint_bytes(self) -> int:
        """|A_b| as anchored: b, CH_b, MR_b, r_b, R_RLI, v_RLI, e, v_b, ts_b, sigma_b."""
        return 8 + self.c.ch.digest_size + 32 + self.c.ch.digest_size + 32 + 8 + 8 + 8 + 8 + self.c.sig.sig_size
