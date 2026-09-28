"""Generic per-request redaction pipeline parameterized by a BaselineSpec (one Table IV/V row)."""
import os
import time
from dataclasses import dataclass

from ..protocol.ledger import Ledger
from ..protocol.types import RedactionRecord, Request


@dataclass
class BaselineSpec:
    ref: int
    label: str
    classical_sig: bool  # original instantiation uses classical signatures
    validate: str  # "sig" | "policy+sig"
    authorize: str  # "none" | "threshold_sign" | "policy" | "dch_approve" | "maabe_threshold"
    adapt: str  # "central" | "threshold"
    audit: str | None  # None | "threshold_sigs" | "sig_hash" | "vds_per_record" | "light"
    onchain: str  # "hash" | "hash+sig"
    grounded: str
    note: str = ""


class PerRequestBaseline:
    """Every request is validated, authorized, adapted and anchored individually.

    pq_adapted=True follows the paper's methodology (classical signatures -> ML-DSA-65, classical CH -> PQCH);
    pq_adapted=False is the 'original classical instantiation' used for reference in Exp. 4 and should be
    run on a Ledger built with Crypto(classical_sigs=True).
    """

    def __init__(self, spec: BaselineSpec, ledger: Ledger, pq_adapted=True):
        self.spec, self.L, self.c = spec, ledger, ledger.c
        self.pq_adapted = pq_adapted
        self.name = spec.label + ("" if pq_adapted else " (classical)")
        self.records: list[RedactionRecord] = []
        self._rid = 0
        self._approvals: dict = {}

    # ------------------------------------------------------------ requester side
    def make_request(self, requester, tid, m_new, op="modify", tamper=""):
        c, L = self.c, self.L
        rho = os.urandom(32)
        R = Request(requester, tid, op, c.H(m_new, rho), L.e, int(time.time() * 1000), os.urandom(16), m_new, rho,
                    tamper=tamper)
        sk = L.requesters[requester].sk if tamper != "sig" else L.requesters[(requester + 1) % len(L.requesters)].sk
        R.sigma_R = c.sign(sk, c.H(R.ID_r, R.TID, R.op, R.D_new, R.e, R.ts_r, R.n_r))
        if self.spec.authorize == "dch_approve":  # requester also signs the new transaction tx'
            R.aux["sig_tx_new"] = c.sign(sk, c.H("tx'", R.D_new))
        return R

    # ------------------------------------------------------------ request validation (Table IV col. 1)
    def validate(self, R):
        c, L = self.c, self.L
        if R.TID not in L.txs:
            return None
        if "policy" in self.spec.validate:
            c.policy_auth()
        if not c.verify(L.requesters[R.ID_r].pk, c.H(R.ID_r, R.TID, R.op, R.D_new, R.e, R.ts_r, R.n_r), R.sigma_R):
            return None
        return R

    # ------------------------------------------------------------ authorization (per request)
    def authorize(self, R) -> bool:
        c, L, mode = self.c, self.L, self.spec.authorize
        msg = c.H("auth", R.TID, R.D_new, R.n_r)
        if mode == "none":
            return True
        if mode == "threshold_sign":  # m t (T_S + T_V)
            sigs = [c.sign(L.committee[k].sk, msg) for k in range(L.t)]
            self._approvals[R.n_r] = sigs  # kept as the record's authorization evidence
            return all(c.verify(L.committee[k].pk, msg, s) for k, s in enumerate(sigs))
        if mode == "policy":  # m T_Pol
            c.policy_auth()
            return True
        if mode == "dch_approve":  # t full nodes each check the signatures of tx and tx' (Li et al. [1], III-C3 step 3)
            pk = L.requesters[R.ID_r].pk
            h_req = c.H(R.ID_r, R.TID, R.op, R.D_new, R.e, R.ts_r, R.n_r)
            return all(c.verify(pk, h_req, R.sigma_R) and c.verify(pk, c.H("tx'", R.D_new), R.aux["sig_tx_new"])
                       for _ in range(L.t))
        if mode == "maabe_threshold":  # TODO-VERIFY against [15]
            c.policy_auth()
            return all(c.verify(L.committee[k].pk, msg, c.sign(L.committee[k].sk, msg)) for k in range(L.t))
        raise ValueError(mode)

    # ------------------------------------------------------------ execution (per request)
    def execute(self, R):
        c, L = self.c, self.L
        tx = L.txs[R.TID]
        bt = L.batches[tx.b]
        old_root, old_r, v_old = bt.tree.root, bt.r, bt.v
        c.counts["T_H"] += bt.tree.update({tx.pos: c.H(tx.I, R.D_new)})  # O(log N) per request
        if self.spec.adapt == "threshold":
            shares = [c.ch_part_adapt(L.td[k + 1], old_root, old_r, bt.tree.root) for k in range(L.t)]
            new_r = c.ch_combine(shares, old_r)
        else:
            new_r = c.ch_adapt(L.T_full, old_root, old_r, bt.tree.root)
        assert c.ch_hash(L.pk_ch, bt.tree.root, new_r) == bt.ch
        bt.r, bt.v = new_r, bt.v + 1
        D_old = tx.D
        tx.m, tx.rho, tx.D = R.m_new, R.rho_new, R.D_new
        L._index_put(tx)
        state = 32 + (self.c.sig.sig_size if self.spec.onchain == "hash+sig" else 0)
        L.chain.anchor("per_request_redaction", state, phase=5, scheme=self.spec.label, redactions=1)
        self._rid += 1
        rr = RedactionRecord(self._rid.to_bytes(8, "big"), R.TID, b"", tx.PID, D_old, tx.D, v_old, bt.v,
                             c.H(R.TID, D_old, tx.D, v_old), int(time.time()), tx.b, tx.pos, L.e,
                             {"approvals": self._approvals.pop(R.n_r, []), "auth_msg": c.H("auth", R.TID, R.D_new, R.n_r),
                              "sig": c.sign(L.audit_svc.sk, c.H(R.TID, tx.D)) if self.spec.audit else b""})
        self.records.append(rr)
        return rr

    def process(self, R):
        """Full per-request pipeline (Exp. 1): validate -> authorize -> execute."""
        if self.validate(R) is None or not self.authorize(R):
            return None
        rr = self.execute(R)
        self.L.rli.finalize()
        return rr

    # ------------------------------------------------------------ audit (Exp. 3/4)
    def audit(self, records):
        """Per-record evidence: an individual Merkle path per record plus the scheme's per-record proof."""
        if self.spec.audit is None:
            raise NotImplementedError(f"{self.name} has no audit stage (N/A in Table IV)")
        c, L = self.c, self.L
        depth = len(next(iter(L.batches.values())).tree.levels) - 1
        per = 128 + 32 * depth
        sig = c.sig.sig_size
        extra = {"threshold_sigs": L.t * sig, "sig_hash": sig + 32, "vds_per_record": sig + 3 * 256, "light": 64}
        per += extra[self.spec.audit]
        body_sig = c.sign(L.audit_svc.sk, c.H("resp", len(records)))
        return {"records": records, "sig": body_sig, "nbytes": len(records) * per + sig}

    def verify_audit(self, resp, deep=False, state_transition=True):
        c, L, mode = self.c, self.L, self.spec.audit
        c.verify(L.audit_svc.pk, c.H("resp", len(resp["records"])), resp["sig"])
        depth = len(next(iter(L.batches.values())).tree.levels) - 1
        out = {}
        for rr in resp["records"]:
            c.counts["T_H"] += depth + 1  # individual Merkle path
            ok = True
            if mode == "threshold_sigs":  # O(n_Q) t T_V
                msg = rr.pbrp["auth_msg"]
                ok = len(rr.pbrp["approvals"]) >= L.t and all(c.verify(L.committee[k].pk, msg, s) for k, s in enumerate(rr.pbrp["approvals"]))
            elif mode in ("sig_hash", "vds_per_record"):  # O(n_Q)(T_V + T_H)
                ok = c.verify(L.audit_svc.pk, c.H(rr.TID, rr.D_new), rr.pbrp["sig"])
                c.counts["T_H"] += 1 if mode == "sig_hash" else 3  # + non-membership freshness check
            elif mode == "light":  # TODO-VERIFY [20]
                c.counts["T_H"] += 2
            if state_transition:
                c.counts["T_H"] += 1
            out[rr.RID] = ok and c.H(rr.TID, rr.D_old, rr.D_new, rr.v_b) == rr.h_pbrp
        return out
