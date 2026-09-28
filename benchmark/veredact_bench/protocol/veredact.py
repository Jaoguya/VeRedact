"""VeRedact-PQ: Phases 3-6 on top of the shared ledger (Phases 1-2).

Variants (paper, Sec. Evaluation):
  batching   = "abrrr" (default) | "fixed" (Fixed-Batch) | "none" (Per-Request)
  bimc       = True  | False (No-BIMC: independent Merkle update + PQCH adaptation per modification)
  rezk       = False | True  (Re-ZK: committee re-verifies each PQZK proof instead of alpha_i)
  per_record = False | True  (Per-Record Evidence: individual paths + full auth evidence per record)
"""
import math
import os
import time
from dataclasses import dataclass, field

from ..ds.merkle import MerkleTree, verify_multiproof, verify_proof
from .ledger import Ledger
from .types import BatchAuth, RedactionRecord, Request, ValidatedRequest


@dataclass
class Rejection:
    reason: str
    stage: str


@dataclass
class AuditResponse:
    body: dict
    sigma: bytes
    nbytes: int
    records: list = field(default_factory=list)


class VeRedactPQ:
    name = "VeRedact-PQ"

    def __init__(self, ledger: Ledger, batching="abrrr", bimc=True, rezk=False, per_record=False,
                 B_min=8, B_max=256, T_max_ms=500.0, fixed_B=64):
        self.L, self.c = ledger, ledger.c
        self.batching, self.bimc, self.rezk, self.per_record = batching, bimc, rezk, per_record
        self.B_min, self.B_max, self.T_max_ms, self.fixed_B = B_min, B_max, T_max_ms, fixed_B
        self.queue: list[ValidatedRequest] = []
        self.evidence: dict[bytes, dict] = {}  # off-ledger evidence store: RID -> full evidence
        self.auths: dict[bytes, BatchAuth] = {}
        self.records: list[RedactionRecord] = []
        self._rid = 0

    # ============================================================ requester side
    def make_request(self, requester: int, tid: bytes, m_new: bytes, op="modify", tamper="") -> Request:
        """Requester prepares R_i, signs it (T_S) and proves policy compliance (T_ZP). Excluded from T_val."""
        L, c = self.L, self.c
        tx = L.txs.get(tid)
        rho_new = os.urandom(32)
        R = Request(ID_r=requester, TID=tid, op=op, D_new=c.H(m_new, rho_new), e=L.e,
                    ts_r=int(time.time() * 1000), n_r=os.urandom(16), m_new=m_new, rho_new=rho_new, tamper=tamper)
        if tx is not None:
            bt = L.batches[tx.b]
            R.x = self._statement(R, tx, bt.v)
            eligible = tamper != "zk"
            R.proof = c.zk_prove(L.zk_params, R.x, {"cred": requester}, lambda x, w: eligible)
        sk = L.requesters[requester].sk if tamper != "sig" else L.requesters[(requester + 1) % len(L.requesters)].sk
        R.sigma_R = c.sign(sk, self._hR(R))
        return R

    def _hR(self, R):
        return self.c.H(R.ID_r, R.TID, R.op, R.D_new, R.e, R.ts_r, R.n_r)

    def _statement(self, R, tx, v_b):
        pol = self.L.policies[tx.PID]
        return self.c.H(R.ID_r, R.TID, tx.I, tx.D, R.D_new, pol.C_P, R.op, tx.b, v_b, tx.e_i, R.e, R.ts_r, R.n_r)

    # ============================================================ Phase 3 (VPS)
    def validate(self, R: Request, t_submit: float = 0.0):
        """Staged admission -> SA-RLI resolution -> PQ auth -> public policy -> PQZK -> attestation."""
        L, c = self.L, self.c
        # Step 1: admission + authenticated resolution
        if R.e != L.e or R.op not in ("modify", "delete"):
            return Rejection("format/epoch", "admission")
        tau = c.PRF(L.K_idx, R.TID)
        hit = L.rli.lookup(tau)
        if hit is None:
            return Rejection("nonexistent target", "lookup")
        entry, s, pos_s, shard_proof, global_proof = hit
        c.counts["T_H"] += len(shard_proof) + len(global_proof)  # membership against R_s and R_RLI
        tx = L.txs[R.TID]
        bt = L.batches[tx.b]
        c.counts["T_H"] += len(bt.tree.levels) - 1  # leaf L_i against MR_b
        # Step 2: PQ requester authentication; nonce consumed only after success
        if not c.verify(L.requesters[R.ID_r].pk, self._hR(R), R.sigma_R):
            return Rejection("bad requester signature", "auth")
        if (R.ID_r, R.n_r) in L.used_nonces:
            return Rejection("replay", "auth")
        L.used_nonces.add((R.ID_r, R.n_r))
        # Step 3: public policy + state
        pol = L.policies[tx.PID]
        if c.H(pol.PID, pol.body, pol.v, pol.e_P) != pol.C_P or R.op not in pol.ops or R.tamper == "policy":
            return Rejection("public policy", "policy")
        if R.tamper == "stale":
            return Rejection("stale state", "policy")
        # Step 4: PQZK private policy
        if R.x != self._statement(R, tx, bt.v) or not c.zk_verify(L.zk_params, R.x, R.proof):
            return Rejection("PQZK", "zk")
        # Step 5: validated-request commitment + attestation
        self._rid += 1
        RID = self._rid.to_bytes(8, "big")
        h_proof = c.H(R.proof)
        C_VR = c.H(RID, self._hR(R), tx.I, tx.D, pol.C_P, tx.b, tx.pos, bt.v, tx.e_i, h_proof)
        alpha = c.sign(L.vps.sk, c.H(RID, C_VR, L.e))
        vr = ValidatedRequest(RID, C_VR, tx.b, tx.pos, tx.PID, bt.v, tx.e_i, L.e, R.sigma_R, h_proof, alpha, R, t_submit)
        self.evidence[RID] = {"R": R, "x": R.x, "proof": R.proof}
        return vr

    # ============================================================ Phase 4 (ABRRR + committee)
    def target_batch_size(self, arrival_rate: float) -> int:
        """B_e* = min{B_max, max{B_min, ceil(B_hat)}}; B_hat = expected arrivals within T_max."""
        if self.batching == "none":
            return 1
        if self.batching == "fixed":
            return self.fixed_B
        b_hat = arrival_rate * self.T_max_ms / 1000.0 + len(self.queue)
        return min(self.B_max, max(self.B_min, math.ceil(b_hat)))

    def authorize(self, batch: list[ValidatedRequest]):
        L, c = self.L, self.c
        eligible = []
        for vr in batch:  # Step 2: attestation + freshness
            if not c.verify(L.vps.pk, c.H(vr.RID, vr.C_VR, vr.e), vr.alpha):
                continue
            if self.rezk:  # Re-ZK variant: re-verify the PQZK proof
                ev = self.evidence[vr.RID]
                if not c.zk_verify(L.zk_params, ev["x"], ev["proof"]):
                    continue
            tx = L.txs[vr.req.TID]
            if (tx.D, L.batches[vr.b].v, tx.e_i) != (self._D_at_validation(vr), vr.v_b, vr.e_i) or vr.e != L.e:
                continue
            eligible.append(vr)
        if not eligible:
            return None
        eligible.sort(key=lambda v: v.RID)
        leaves = [c.H(v.RID, v.C_VR, v.h_proof, v.alpha, v.b, v.v_b, v.e_i, v.e) for v in eligible]
        tree = MerkleTree(leaves)
        c.counts["T_H"] += tree.hash_ops[0]
        BID = os.urandom(16)
        ts = int(time.time())
        C_B = c.H(BID, L.e, len(eligible), tree.root, ts)
        msg = c.H(C_B, L.e)
        approvals = []
        for k in range(L.t):  # Step 4: t distinct PQ signatures (+ verification)
            sig = c.sign(L.committee[k].sk, msg)
            if c.verify(L.committee[k].pk, msg, sig):
                approvals.append((k, sig))
        if len(approvals) < L.t:
            return None
        auth = BatchAuth(BID, C_B, tree.root, approvals, L.e, ts, eligible, leaves,
                         {v.RID: tree.proof(i) for i, v in enumerate(eligible)})
        self.auths[BID] = auth
        L.chain.anchor("abrrr_authorization", 16 + 32 + 32 + 8, phase=4)  # digest of Auth_e^B
        return auth

    def _D_at_validation(self, vr):
        # D_i as bound in C_VR; recomputed from the ledger when the state is unchanged
        return self.L.txs[vr.req.TID].D

    # ============================================================ Phase 5 (Algorithm 1)
    def execute(self, auth: BatchAuth):
        L, c = self.L, self.c
        by_batch: dict[int, list] = {}
        for vr in auth.members:
            by_batch.setdefault(vr.b, []).append(vr)
        prepared, finalized = [], []
        for b, reqs in by_batch.items():
            bt = L.batches[b]
            seen, exe = set(), []
            for vr in reqs:  # conflicts: one resulting commitment per transaction per round
                if vr.req.TID in seen or bt.v != vr.v_b:
                    continue
                if c.H(vr.req.m_new, vr.req.rho_new) != vr.req.D_new:
                    continue
                seen.add(vr.req.TID)
                exe.append(vr)
            if not exe:
                continue
            groups = [exe] if self.bimc else [[v] for v in exe]
            for grp in groups:
                old_root, old_r = bt.tree.root, bt.r
                changes = {}
                for vr in grp:
                    tx = L.txs[vr.req.TID]
                    changes[tx.pos] = c.H(tx.I, vr.req.D_new)  # L_i' = H(I_i || D_i')
                c.counts["T_H"] += bt.tree.update(changes)
                new_root = bt.tree.root
                shares = [c.ch_part_adapt(L.td[k + 1], old_root, old_r, new_root, auth.BID) for k in range(L.t)]
                new_r = c.ch_combine(shares, old_r)
                if c.ch_hash(L.pk_ch, new_root, new_r) != bt.ch:
                    raise RuntimeError(f"PQCH adaptation failed for batch {b}")
                bt.r, bt.v = new_r, bt.v + 1
                prepared.append((b, grp, old_root, new_root, bt.v - 1, bt.v))
        for b, grp, old_root, new_root, v_old, v_new in prepared:  # atomic finalization
            for vr in grp:
                tx = L.txs[vr.req.TID]
                D_old = tx.D
                tx.m, tx.rho, tx.D, tx.e_i = vr.req.m_new, vr.req.rho_new, vr.req.D_new, L.e
                L._index_put(tx)
                finalized.append((vr, tx, D_old, b, v_old, v_new, old_root, new_root))
        if not prepared:
            return []
        R = L.rli.finalize()
        c.counts["T_H"] += L.rli.last_hash_ops
        for b in {p[0] for p in prepared}:
            L.checkpoints[b] = L._checkpoint(b, R)
        n_cp = len(prepared)  # one anchored checkpoint per root transition (|Omega_e| with BIMC)
        L.chain.anchor("redaction_finalization", n_cp * L.checkpoint_bytes() + 32, phase=5, transitions=n_cp,
                       redactions=len(finalized))
        out = []
        for vr, tx, D_old, b, v_old, v_new, old_root, new_root in finalized:
            pbrp = {"RID": vr.RID, "eta": auth.leaves[auth.members.index(vr)], "MP_B": auth.proofs[vr.RID],
                    "BID": auth.BID, "I": tx.I, "D": D_old, "D_new": tx.D, "b": b, "pos": tx.pos,
                    "v_b": v_old, "v_b_new": v_new, "MR": old_root, "MR_new": new_root, "CH": L.batches[b].ch,
                    "e": L.e, "vr": vr}
            h_pbrp = self.pbrp_digest(vr.RID, auth.BID, tx.I, D_old, tx.D, b, tx.pos, v_old, v_new, old_root, new_root)
            rr = RedactionRecord(vr.RID, tx.TID, auth.BID, tx.PID, D_old, tx.D, v_old, v_new, h_pbrp,
                                 int(time.time()), b, tx.pos, L.e, pbrp)
            self.records.append(rr)
            out.append(rr)
        return out

    # ============================================================ Phase 6 (RAI + audit)
    def index_records(self, records=None):
        L, c = self.L, self.c
        for rr in records if records is not None else self.records:
            tau = c.PRF(L.K_A, rr.TID) + rr.RID  # historical: one entry per redaction
            rr.pbrp["tau_A"] = tau
            L.rai.put(tau, self.rai_entry(rr))
        R = L.rai.finalize()
        c.counts["T_H"] += L.rai.last_hash_ops
        L.chain.anchor("rai_checkpoint", 8 + 32 + 8 + 8, phase=6)
        return c.H(L.e, R, L.rai.snapshot, int(time.time()))  # CP_e^A

    def audit(self, records: list[RedactionRecord], qtype="authorization"):
        """Build Resp_j^A for a resolved record set R_{Q_j} (query resolution done by the caller)."""
        L, c = self.L, self.c
        Q = c.H("Q", qtype, len(records), os.urandom(8))
        by_shard: dict[int, list] = {}
        for rr in records:
            tau = rr.pbrp["tau_A"]
            by_shard.setdefault(L.rai.sid(tau), []).append(L.rai.shards[L.rai.sid(tau)].pos[tau])
        entries_bytes = 128 * len(records)
        if self.per_record:  # individual path + complete authorization evidence per record
            paths = sum(len(L.rai.shards[s].tree.proof(p)) + len(L.rai.global_tree.proof(s))
                        for s, ps in by_shard.items() for p in ps)
            auth_bytes = len(records) * self._auth_bytes()
            proof_bytes = 32 * paths
        else:  # query-scoped multiproof + shared batch evidence once per BID
            mp = {s: L.rai.shards[s].tree.multiproof(ps) for s, ps in by_shard.items()}
            gmp = L.rai.global_tree.multiproof(list(by_shard))
            proof_bytes = 32 * (sum(len(v) for v in mp.values()) + len(gmp))
            auth_bytes = len({rr.BID for rr in records}) * self._auth_bytes()
        rec_bytes = len(records) * (32 * 8 + L.c.sig.sig_size)  # per-record: eta, MP_B, C_VR, alpha, ...
        body = {"Q": Q, "records": records, "R_RAI": L.rai.root, "v_A": L.rai.snapshot}
        sigma = c.sign(L.audit_svc.sk, c.H(Q, len(records), L.rai.root, L.rai.snapshot))
        nbytes = entries_bytes + proof_bytes + auth_bytes + rec_bytes + L.c.sig.sig_size
        return AuditResponse(body, sigma, nbytes, records)

    def _auth_bytes(self):
        return 16 + 32 + 32 + 8 + 8 + self.L.t * (8 + self.c.sig.sig_size)

    def pbrp_digest(self, RID, BID, I, D, D_new, b, pos, v_b, v_b_new, MR, MR_new) -> bytes:
        return self.c.H(RID, BID, I, D, D_new, b, pos, v_b, v_b_new, MR, MR_new)

    def rai_entry(self, rr) -> bytes:
        tau = rr.pbrp["tau_A"]
        return self.c.H(tau, rr.RID, rr.BID, rr.PID, rr.e, rr.v_b, rr.v_b_new, rr.h_pbrp, rr.ts_red)

    def verify_audit(self, resp: AuditResponse, deep=False, state_transition=True):
        """AuditVerify: returns {RID: accepted}; each record is accepted or rejected individually."""
        L, c = self.L, self.c
        body = resp.body
        if not c.verify(L.audit_svc.pk, c.H(body["Q"], len(body["records"]), body["R_RAI"], body["v_A"]), resp.sigma):
            return {rr.RID: False for rr in resp.records}
        # RAI multiproof (hash-based)
        by_shard = {}
        for rr in resp.records:
            s = L.rai.sid(rr.pbrp["tau_A"])
            by_shard.setdefault(s, {})[L.rai.shards[s].pos[rr.pbrp["tau_A"]]] = L.rai.shards[s].entries[rr.pbrp["tau_A"]]
        for s, leaves in by_shard.items():
            tree = L.rai.shards[s].tree
            _, ops = verify_multiproof(tree.root, leaves, tree.multiproof(list(leaves)), len(tree.levels) - 1)
            c.counts["T_H"] += ops
        # shared batch evidence once per BID (per record for the Per-Record variant)
        checked = {}
        result = {}
        for rr in resp.records:
            key = rr.BID if not self.per_record else (rr.BID, rr.RID)
            if key not in checked:
                auth = self.auths[rr.BID]
                msg = c.H(auth.C_B, auth.e)
                checked[key] = all(c.verify(L.committee[k].pk, msg, s) for k, s in auth.approvals)
            ok = checked[key]
            p = rr.pbrp
            ok &= verify_proof(self.auths[rr.BID].R_VR, p["eta"], self.auths[rr.BID].members.index(p["vr"]), p["MP_B"])
            c.counts["T_H"] += len(p["MP_B"]) + 1
            vr = p["vr"]
            ok &= c.verify(L.vps.pk, c.H(vr.RID, vr.C_VR, vr.e), vr.alpha)  # normal audit: alpha_i
            if state_transition:
                c.counts["T_H"] += 2
                ok &= c.ch_hash(L.pk_ch, p["MR_new"], L.checkpoints[p["b"]].r) == p["CH"] if p["v_b_new"] == L.batches[p["b"]].v else True
            if deep:
                ev = self.evidence[rr.RID]
                ok &= c.zk_verify(L.zk_params, ev["x"], ev["proof"]) and c.H(ev["proof"]) == vr.h_proof
            # H(PBRP_i) must bind the returned transition (catches modified D_i' / substituted evidence)
            ok &= self.pbrp_digest(rr.RID, rr.BID, p["I"], rr.D_old, rr.D_new, p["b"], p["pos"], rr.v_b, rr.v_b_new,
                                   p["MR"], p["MR_new"]) == rr.h_pbrp
            # the returned record must reproduce its authenticated RAI entry (catches modified/stale fields)
            tau = p["tau_A"]
            ok &= self.rai_entry(rr) == L.rai.shards[L.rai.sid(tau)].entries[tau]
            result[rr.RID] = bool(ok)
        return result
