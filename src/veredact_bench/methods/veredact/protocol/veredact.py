"""VeRedact-PQ: Phases 3-6 on top of the shared ledger (Phases 1-2). One configuration: ABRRR batching,
BIMC coalescing, attestation-based Phase 4, query-scoped audit evidence (no internal variants)."""

import math
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np

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

    def __init__(self, ledger: Ledger, cfg: dict):
        v = cfg["veredact"]
        self.L, self.c = ledger, ledger.c
        self.pending_anchor = []  # futures of ledger operations (ledger_ms is measured from these)
        self.last_finalization = None
        self.B_min, self.B_max, self.T_max_ms = v["B_min"], v["B_max"], v["T_max_ms"]
        self.evidence: dict[bytes, dict] = {}  # off-ledger evidence store: RID -> full evidence
        self.auths: dict[bytes, BatchAuth] = {}
        self.records: list[RedactionRecord] = []
        self._rid = 0
        self._admit = threading.Lock()

    # ============================================================ requester side
    def make_request(self, requester: int, tid: bytes, m_new: bytes, op="modify", tamper="") -> Request:
        """Requester prepares R_i, signs it (T_S) and proves policy compliance (T_ZP). Excluded from T_val."""
        L, c = self.L, self.c
        tx = L.txs.get(tid)
        rho_new = os.urandom(32)
        R = Request(
            ID_r=requester,
            TID=tid,
            op=op,
            D_new=c.H(m_new, rho_new),
            e=L.e,
            ts_r=int(time.time() * 1000),
            n_r=os.urandom(16),
            m_new=m_new,
            rho_new=rho_new,
            tamper=tamper,
        )
        if tx is not None:
            bt = L.batches[tx.b]
            R.v_b = bt.v
            R.x = self._statement(R, tx, bt.v)
            # fault "zk": the requester lacks a valid credential -> a proof over a non-registered witness
            forged = int.from_bytes(os.urandom(15), "big") if tamper == "zk" else None
            R.proof = c.zk_prove(requester, R.x, L.policies[tx.PID].threshold, R.ts_r // 1000, forged)
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
        entry, s, _, shard_proof, global_proof = hit
        c.counts["T_H"] += len(shard_proof) + len(global_proof)  # membership against R_s and R_RLI
        tx = L.txs[R.TID]
        bt = L.batches[tx.b]
        c.counts["T_H"] += len(bt.tree.levels) - 1  # leaf L_i against MR_b
        # Step 2: PQ requester authentication; nonce consumed only after success
        if not c.verify(L.requesters[R.ID_r].pk, self._hR(R), R.sigma_R):
            return Rejection("bad requester signature", "auth")
        with self._admit:  # VPS workers run concurrently (Exp. 1): check-and-consume must be atomic
            if (R.ID_r, R.n_r) in L.used_nonces:
                return Rejection("replay", "auth")
            L.used_nonces.add((R.ID_r, R.n_r))
        # Step 3: public policy + state
        pol = L.policies[tx.PID]
        if c.H(pol.PID, pol.body, pol.v, pol.e_P) != pol.C_P or R.op not in pol.ops or R.tamper == "policy":
            return Rejection("public policy", "policy")
        if R.tamper == "stale":
            return Rejection("stale state", "policy")
        if R.v_b != bt.v:  # honest request overtaken by a redaction of its batch: returned for revalidation
            return Rejection("stale state", "freshness")
        # Step 4: PQZK private policy (threshold from the authenticated policy, ts_r from the signed request)
        if R.x != self._statement(R, tx, bt.v) or not c.zk_verify(R.ID_r, R.x, R.proof, pol.threshold, R.ts_r // 1000):
            return Rejection("PQZK", "zk")
        # Step 5: validated-request commitment + attestation
        with self._admit:
            self._rid += 1
            RID = self._rid.to_bytes(8, "big")
        h_proof = c.H(R.proof)
        C_VR = c.H(RID, self._hR(R), tx.I, tx.D, pol.C_P, tx.b, tx.pos, bt.v, tx.e_i, h_proof)
        alpha = c.sign(L.vps.sk, c.H(RID, C_VR, L.e))
        vr = ValidatedRequest(
            RID, C_VR, tx.b, tx.pos, tx.PID, bt.v, tx.e_i, L.e, R.sigma_R, h_proof, alpha, R, t_submit
        )
        self.evidence[RID] = {"R": R, "x": R.x, "proof": R.proof}
        # admission to Q_e: signed receipt rc_i = Sign(sk_V, H(RID || H(R_i) || ts_rc)) returned to the requester
        ts_rc = int(time.time() * 1000)
        vr.receipt = (ts_rc, c.sign(L.vps.sk, c.H(RID, self._hR(R), ts_rc)))
        return vr

    # ============================================================ Phase 4 (ABRRR + committee)
    def target_batch_size(self, arrival_rate: float) -> int:
        """B_e* = min{B_max, max{B_min, ceil(B_hat)}}. The manuscript writes B_hat = f(lambda_e, |Q_e|, T_max)
        without defining f; here f = lambda_e * T_max (expected arrivals within T_max). |Q_e| is applied by
        the batcher (Exp. 1 closes a batch once |Q_e| >= B_e*); adding it to B_hat would keep B_hat above
        |Q_e| forever, so batches would only close at T_max or B_max."""
        b_hat = arrival_rate * self.T_max_ms / 1000.0
        return min(self.B_max, max(self.B_min, math.ceil(b_hat)))

    def authorize(self, batch: list[ValidatedRequest]):
        """Phase 4. self.last_breakdown (ms): attestation verification (+ C_VR reconstruction), state freshness,
        batch commitment, committee signing + verification."""
        L, c = self.L, self.c
        bd = {"attest_ms": 0.0, "fresh_ms": 0.0, "commit_ms": 0.0, "committee_ms": 0.0}
        self.last_breakdown = bd
        eligible = []
        for vr in batch:  # Step 2: attestation + freshness
            t0 = time.perf_counter()
            ok = c.verify(L.vps.pk, c.H(vr.RID, vr.C_VR, vr.e), vr.alpha)
            if ok:  # the supporting evidence must reconstruct C_VR (requester, policy, PQZK-proof hash)
                ev, tx = self.evidence[vr.RID], L.txs[vr.req.TID]
                h_proof = c.H(ev["proof"])
                ok = h_proof == vr.h_proof and vr.C_VR == c.H(
                    vr.RID,
                    self._hR(vr.req),
                    tx.I,
                    self._D_at_validation(vr),
                    L.policies[vr.PID].C_P,
                    vr.b,
                    vr.pos,
                    vr.v_b,
                    vr.e_i,
                    h_proof,
                )
            t1 = time.perf_counter()
            bd["attest_ms"] += (t1 - t0) * 1000
            if not ok:
                continue
            tx = L.txs[vr.req.TID]
            fresh = (tx.D, L.batches[vr.b].v, tx.e_i) == (self._D_at_validation(vr), vr.v_b, vr.e_i) and vr.e == L.e
            bd["fresh_ms"] += (time.perf_counter() - t1) * 1000
            if fresh:
                eligible.append(vr)
        if not eligible:
            return None
        t2 = time.perf_counter()
        eligible.sort(key=lambda v: v.RID)
        leaves = [c.H(v.RID, v.C_VR, v.h_proof, v.alpha, v.b, v.v_b, v.e_i, v.e) for v in eligible]
        tree = MerkleTree(leaves)
        c.counts["T_H"] += tree.hash_ops[0]
        BID = os.urandom(16)
        ts = int(time.time())
        C_B = c.H(BID, L.e, len(eligible), tree.root, ts)
        msg = c.H(C_B, L.e)
        t3 = time.perf_counter()
        bd["commit_ms"] = (t3 - t2) * 1000
        approvals = []
        for k in range(L.t):  # Step 4: t distinct PQ signatures (+ verification)
            sig = c.sign(L.committee[k].sk, msg)
            if c.verify(L.committee[k].pk, msg, sig):
                approvals.append((k, sig))
        bd["committee_ms"] = (time.perf_counter() - t3) * 1000
        if len(approvals) < L.t:
            return None
        auth = BatchAuth(
            BID,
            C_B,
            tree.root,
            approvals,
            L.e,
            ts,
            eligible,
            leaves,
            {v.RID: tree.proof(i) for i, v in enumerate(eligible)},
        )
        self.auths[BID] = auth
        self.pending_anchor.append(
            L.anchor.submit(
                "abrrr_authorization",
                bid=BID.ljust(32, b"\0"),
                digest=c.H(BID, C_B, tree.root, *[s for _, s in approvals]),
            )
        )
        return auth

    def _D_at_validation(self, vr):
        # D_i as bound in C_VR; recomputed from the ledger when the state is unchanged
        return self.L.txs[vr.req.TID].D

    # ============================================================ Phase 5 (Algorithm 1)
    def execute(self, auth: BatchAuth):
        L, c = self.L, self.c
        # Step 1: verify Auth_e^B (t committee approvals over H(C_B || e)) and every PBRP_i^auth (eta_i in R_e^VR)
        msg = c.H(auth.C_B, auth.e)
        if len({k for k, _ in auth.approvals}) < L.t or not all(
            c.verify(L.committee[k].pk, msg, sig) for k, sig in auth.approvals
        ):
            return []
        by_batch: dict[int, list] = {}
        for i, vr in enumerate(auth.members):
            c.counts["T_H"] += len(auth.proofs[vr.RID]) + 1
            if not verify_proof(auth.R_VR, auth.leaves[i], i, auth.proofs[vr.RID]):
                continue
            by_batch.setdefault(vr.b, []).append(vr)
        prepared, finalized, groups = [], [], {}
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
            groups[b] = exe  # BIMC: every modification of batch b shares one root transition
        # distributed SIS adaptation for the whole ABRRR round: the combiner prepares (p_j, z_j) for every
        # touched batch j, each of the t members returns S_k Z for the round, the combiner combines.
        if groups:
            jobs = []
            for b, grp in groups.items():
                bt = L.batches[b]
                old_root, old_r = bt.tree.root, bt.r
                changes, old = {}, {}
                for vr in grp:
                    tx = L.txs[vr.req.TID]
                    old[tx.pos] = c.H(tx.I, tx.D)  # L_i = H(I_i || D_i)
                    changes[tx.pos] = c.H(tx.I, vr.req.D_new)  # L_i' = H(I_i || D_i')
                # BIMC: verify the old leaves' compact multiproof MP_b^multi against MR_b, then update
                ok, ops = verify_multiproof(old_root, old, bt.tree.multiproof(sorted(old)), len(bt.tree.levels) - 1)
                c.counts["T_H"] += ops
                if not ok:
                    raise RuntimeError(f"BIMC multiproof failed for batch {b}")
                c.counts["T_H"] += bt.tree.update(changes)
                jobs.append((b, grp, old_root, old_r, bt.tree.root))
            R_old = np.stack([j[3] for j in jobs], axis=1)
            P, Z = c.ch_begin_adapt_many(L.pk_ch, [j[2] for j in jobs], R_old, [j[4] for j in jobs])
            deltas = [c.ch_part_adapt_many(L.td[k + 1], Z) for k in range(L.t)]
            R_new = c.ch_combine_many(P, Z, deltas)
            ok = c.ch_verify_many(L.pk_ch, [L.batches[j[0]].ch for j in jobs], [j[4] for j in jobs], R_new)
            for col, (b, grp, old_root, _, new_root) in enumerate(jobs):
                if not ok[col]:
                    raise RuntimeError(f"PQCH adaptation failed for batch {b}")
                bt = L.batches[b]
                bt.r, bt.v = R_new[:, col].copy(), bt.v + 1
                prepared.append((b, grp, old_root, new_root, bt.v - 1, bt.v, bt.r))
        for b, grp, old_root, new_root, v_old, v_new, new_r in prepared:  # atomic finalization
            for vr in grp:
                tx = L.txs[vr.req.TID]
                D_old = tx.D
                tx.m, tx.rho, tx.D, tx.e_i = vr.req.m_new, vr.req.rho_new, vr.req.D_new, L.e
                L._index_put(tx)
                finalized.append((vr, tx, D_old, b, v_old, v_new, old_root, new_root, new_r))
        if not prepared:
            return []
        R = L.rli.finalize()
        c.counts["T_H"] += L.rli.last_hash_ops
        for b in {p[0] for p in prepared}:
            L.checkpoints[b] = L._checkpoint(b, R)
        # one anchored checkpoint per root transition (|Omega_e| with BIMC), finalized atomically
        touched = [p[0] for p in prepared]
        self.last_finalization = L.anchor.submit(
            "redaction_finalization",
            bid=auth.BID.ljust(32, b"\0"),
            batches=touched,
            sigs=[L.checkpoints[b].sigma for b in touched],
        )
        self.pending_anchor.append(self.last_finalization)
        out = []
        for vr, tx, D_old, b, v_old, v_new, old_root, new_root, new_r in finalized:
            pbrp = {
                "RID": vr.RID,
                "eta": auth.leaves[auth.members.index(vr)],
                "MP_B": auth.proofs[vr.RID],
                "BID": auth.BID,
                "I": tx.I,
                "D": D_old,
                "D_new": tx.D,
                "b": b,
                "pos": tx.pos,
                "v_b": v_old,
                "v_b_new": v_new,
                "MR": old_root,
                "MR_new": new_root,
                "CH": L.batches[b].ch,
                "r_new": new_r,
                "e": L.e,
                "vr": vr,
            }
            h_pbrp = self.pbrp_digest(vr.RID, auth.BID, tx.I, D_old, tx.D, b, tx.pos, v_old, v_new, old_root, new_root)
            rr = RedactionRecord(
                vr.RID,
                tx.TID,
                auth.BID,
                tx.PID,
                D_old,
                tx.D,
                v_old,
                v_new,
                h_pbrp,
                int(time.time()),
                b,
                tx.pos,
                L.e,
                pbrp,
            )
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
        ts = int(time.time())
        cp = c.H(L.e, R, L.rai.snapshot, ts)  # CP_e^A
        self.rai_checkpoint = (L.e, R, L.rai.snapshot, ts, cp)  # as anchored on the PBN
        self.pending_anchor.append(L.anchor.submit("rai_checkpoint", epoch=L.e, cp=cp))
        return cp

    def make_query(self, qtype: str, n: int):
        """Auditor side: Q_j^A and its PQ signature sigma_j^A (outside both audit timers)."""
        L, c = self.L, self.c
        Q = c.H("Q", qtype, n, L.e, os.urandom(16), int(time.time() * 1000))  # QID, qtype, scope, e_j, n_j, ts_j
        return Q, c.sign(L.auditor.sk, Q)

    def audit(self, records: list[RedactionRecord], Q: bytes, sigma_Q: bytes):
        """Build Resp_j^A for a resolved record set R_{Q_j} (query resolution done by the caller). The service
        first verifies the registered auditor's signature on Q_j^A."""
        L, c = self.L, self.c
        if not c.verify(L.auditor.pk, Q, sigma_Q):
            raise PermissionError("audit query not signed by a registered auditor")
        by_shard: dict[int, list] = {}
        for rr in records:
            tau = rr.pbrp["tau_A"]
            by_shard.setdefault(L.rai.sid(tau), []).append(L.rai.shards[L.rai.sid(tau)].pos[tau])
        entries_bytes = 128 * len(records)
        # query-scoped multiproof + shared batch evidence once per BID
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

    def verify_audit(self, resp: AuditResponse, Q: bytes, deep=False, state_transition=True):
        """AuditVerify: returns {RID: accepted}; each record is accepted or rejected individually.
        self.last_breakdown (ms): response signature + query binding + RAI checkpoint, RAI multiproof,
        committee approvals, request membership + attestations, state transition (incl. PQCH), PQZK."""
        L, c = self.L, self.c
        body = resp.body
        bd = dict.fromkeys(("response_ms", "rai_mp_ms", "committee_ms", "attest_ms", "state_ms", "zk_ms"), 0.0)
        self.last_breakdown = bd
        t0 = time.perf_counter()
        e, R_cp, v_cp, ts_cp, cp = self.rai_checkpoint
        ok_resp = (
            body["Q"] == Q
            and (body["R_RAI"], body["v_A"]) == (R_cp, v_cp)
            and c.H(e, R_cp, v_cp, ts_cp) == cp
            and c.verify(L.audit_svc.pk, c.H(body["Q"], len(body["records"]), body["R_RAI"], body["v_A"]), resp.sigma)
        )
        bd["response_ms"] = (time.perf_counter() - t0) * 1000
        if not ok_resp:
            return {rr.RID: False for rr in resp.records}
        # RAI multiproof (hash-based)
        t0 = time.perf_counter()
        by_shard = {}
        for rr in resp.records:
            s = L.rai.sid(rr.pbrp["tau_A"])
            by_shard.setdefault(s, {})[L.rai.shards[s].pos[rr.pbrp["tau_A"]]] = L.rai.shards[s].entries[
                rr.pbrp["tau_A"]
            ]
        for s, leaves in by_shard.items():
            tree = L.rai.shards[s].tree
            _, ops = verify_multiproof(tree.root, leaves, tree.multiproof(list(leaves)), len(tree.levels) - 1)
            c.counts["T_H"] += ops
        bd["rai_mp_ms"] = (time.perf_counter() - t0) * 1000
        # shared batch evidence: committee approvals verified once per BID
        checked = {}
        transitions = {}  # (b, MR_b', r_b') -> PQCH check result: once per affected-batch transition
        result = {}
        for rr in resp.records:
            t0 = time.perf_counter()
            key = rr.BID
            if key not in checked:
                auth = self.auths[rr.BID]
                msg = c.H(auth.C_B, auth.e)
                checked[key] = all(c.verify(L.committee[k].pk, msg, s) for k, s in auth.approvals)
            ok = checked[key]
            t1 = time.perf_counter()
            p = rr.pbrp
            ok &= verify_proof(self.auths[rr.BID].R_VR, p["eta"], self.auths[rr.BID].members.index(p["vr"]), p["MP_B"])
            c.counts["T_H"] += len(p["MP_B"]) + 1
            vr = p["vr"]
            ok &= c.verify(L.vps.pk, c.H(vr.RID, vr.C_VR, vr.e), vr.alpha)  # normal audit: alpha_i
            t2 = time.perf_counter()
            if state_transition:
                c.counts["T_H"] += 2  # L_i, L_i' recomputation (per record)
                # PQCH check of the batch transition A_b -> A_b': shared by every record of that transition, so
                # verified once per response (Table IV: state-transition audits add O(|Omega_e|) T_CH, not n_Q)
                tk = (p["b"], p["MR_new"], _raw(p["CH"]), _raw(p["r_new"]))  # exact bytes: no tamper reuses a result
                if tk not in transitions:
                    transitions[tk] = c.ch_verify(L.pk_ch, p["CH"], p["MR_new"], p["r_new"])  # r_b' as in A_b'
                ok &= transitions[tk]
            t3 = time.perf_counter()
            if deep:
                ev = self.evidence[rr.RID]
                ok &= (
                    c.zk_verify(vr.req.ID_r, ev["x"], ev["proof"], L.policies[vr.PID].threshold, vr.req.ts_r // 1000)
                    and c.H(ev["proof"]) == vr.h_proof
                )
            t4 = time.perf_counter()
            bd["committee_ms"] += (t1 - t0) * 1000
            bd["attest_ms"] += (t2 - t1) * 1000
            bd["state_ms"] += (t3 - t2) * 1000
            bd["zk_ms"] += (t4 - t3) * 1000
            # H(PBRP_i) must bind the returned transition (catches modified D_i' / substituted evidence)
            ok &= (
                self.pbrp_digest(
                    rr.RID,
                    rr.BID,
                    p["I"],
                    rr.D_old,
                    rr.D_new,
                    p["b"],
                    p["pos"],
                    rr.v_b,
                    rr.v_b_new,
                    p["MR"],
                    p["MR_new"],
                )
                == rr.h_pbrp
            )
            # the returned record must reproduce its authenticated RAI entry (catches modified/stale fields)
            tau = p["tau_A"]
            ok &= self.rai_entry(rr) == L.rai.shards[L.rai.sid(tau)].entries[tau]
            result[rr.RID] = bool(ok)
        return result


def _raw(x) -> bytes:
    """Exact byte image of a PQCH value or randomness (numpy array) for use as a dictionary key."""
    return x.tobytes() if hasattr(x, "tobytes") else repr(x).encode()
