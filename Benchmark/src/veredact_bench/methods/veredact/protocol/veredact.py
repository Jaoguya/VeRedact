"""VeRedact-PQ: Phases 3-6 on top of the shared ledger (Phases 1-2), as in Overleaf/VeRedact-optimize.tex.

Variants (manuscript ablations; the default "full" is VeRedact-PQ itself):
  full             CORA selection + SFMR execution + attestation-based Phase 4 + SAVER audit
  per-request      each validated request authorized and executed alone (Exp. 1)
  fixed-batch      arrival order, fixed round size veredact.fixed_batch, no CORA (Exp. 1)
  cora-no-sfmr     CORA selection, but an independent Merkle update + PQCH adaptation per request (Exp. 1)
  re-zk            each of the t committee members re-verifies every PQZK proof (Exp. 2)
  shared-evidence  shared audit evidence sent once but re-verified for every dependent record (Exp. 3)
  per-record       complete evidence sent and verified per record (Exp. 3)
"""

import math
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from ..ds.merkle import MerkleTree, verify_multiproof, verify_proof
from .cora import Candidate, cora_select
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

    VARIANTS = ("full", "per-request", "fixed-batch", "cora-no-sfmr", "re-zk", "shared-evidence", "per-record")

    def __init__(self, ledger: Ledger, cfg: dict, variant: str = "full"):
        if variant not in self.VARIANTS:
            raise ValueError(f"unknown VeRedact-PQ variant {variant!r}")
        v = cfg["veredact"]
        self.variant = variant
        self.fixed_B, self.w_ch, self.w_f = v["fixed_batch"], v["cora_w_ch_ms"], v["cora_w_f_ms"]
        self.audit_mode = {"shared-evidence": "shared", "per-record": "per_record"}.get(variant, "saver")
        self.last_exec = {"batches": 0, "frontier": 0}  # |Omega_e| and F_e of the last execute()
        self.L, self.c = ledger, ledger.c
        self.pending_anchor = []  # futures of ledger operations (ledger_ms is measured from these)
        self.last_finalization = None
        self.B_min, self.B_max, self.T_max_ms = v["B_min"], v["B_max"], v["T_max_ms"]
        self.evidence: dict[bytes, dict] = {}  # off-ledger evidence store: RID -> full evidence
        self.auths: dict[bytes, BatchAuth] = {}
        self.records: list[RedactionRecord] = []
        self._rid = 0
        self._admit = threading.Lock()
        self.vcs: set = set()  # auditor's Verified-Context Store: chi(v) of successfully verified shared nodes

    # ============================================================ requester side
    def make_request(self, requester: int, tid: bytes, m_new: bytes, op="modify", tamper="") -> Request:
        """Requester prepares R_i, signs it (T_S) and proves policy compliance (T_ZP). Excluded from T_val."""
        R, job = self.request_skeleton(requester, tid, m_new, op, tamper)
        R.proof, R.sigma_R = self.requester_work(job, counted=True)
        return R

    def request_skeleton(self, requester: int, tid: bytes, m_new: bytes, op="modify", tamper=""):
        """Requester side, cheap part (hashing only): R_i bound to the CURRENT batch version v_b, plus the job
        for the expensive part (PQZK proof + PQ signature). Exp. 1 runs the job in requester processes on their
        own cores (audit A3); everything else calls make_request, which does both here."""
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
        prove = None
        if tx is not None:
            bt = L.batches[tx.b]
            R.v_b, R.h_st = bt.v, self.state_digest(tx)
            R.x = self._statement(R, tx, R.h_st)
            # fault "zk": the requester lacks a valid credential -> a proof over a non-registered witness
            forged = int.from_bytes(os.urandom(15), "big") if tamper == "zk" else None
            prove = (requester, R.x, L.policies[tx.PID].threshold, R.ts_r // 1000, forged)
        signer = requester if tamper != "sig" else (requester + 1) % len(L.requesters)
        return R, (prove, signer, self._hR(R))

    def requester_work(self, job, counted: bool = False):
        """Requester side, expensive part: (PQZK proof or None, PQ signature on H(R_i)). counted=False (requester
        processes) uses the primitives directly, without the parent's operation counters."""
        prove, signer, h = job
        L, c = self.L, self.c
        if counted:
            proof = c.zk_prove(*prove) if prove else b""
            return proof, c.sign(L.requesters[signer].sk, h)
        proof = c.zk.prove(*prove) if prove else b""
        return proof, c.sig.sign(L.requesters[signer].sk, h)

    def _hR(self, R):
        return self.c.H(R.ID_r, R.TID, R.op, R.D_new, R.e, R.ts_r, R.n_r)

    def state_digest(self, tx) -> bytes:
        """h_i^st = H(TID || I || D || pos || enc(State_b)), State_b from batch b's finalized checkpoint A_b. A_b is
        re-signed only when batch b itself changes, so a redaction in another batch leaves h_i^st unchanged."""
        cp = self.L.checkpoints[tx.b]
        return self.c.H(tx.TID, tx.I, tx.D, tx.pos, cp.b, cp.MR, cp.CH, cp.v_b, cp.R_RLI, cp.v_RLI, cp.e)

    def _statement(self, R, tx, h_st):
        """x_i = (ID_r, TID, op, D_i', C_P, h_i^st, e_i, e, ts_r, n_r)."""
        pol = self.L.policies[tx.PID]
        return self.c.H(R.ID_r, R.TID, R.op, R.D_new, pol.C_P, h_st, tx.e_i, R.e, R.ts_r, R.n_r)

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
        h_st = self.state_digest(tx)
        if R.h_st != h_st:  # honest request overtaken by a redaction of its batch: returned for revalidation
            return Rejection("stale state", "freshness")
        # Step 4: state-bound PQZK private policy (threshold from the authenticated policy, ts_r from the request)
        if R.x != self._statement(R, tx, h_st) or not c.zk_verify(R.ID_r, R.x, R.proof, pol.threshold, R.ts_r // 1000):
            return Rejection("PQZK", "zk")
        # Step 5: validated-request commitment + attestation
        with self._admit:
            self._rid += 1
            RID = self._rid.to_bytes(8, "big")
        h_proof = c.H(R.proof)  # h_i^PQ
        C_VR = c.H(RID, self._hR(R), h_st, pol.C_P, h_proof, L.e)
        alpha = c.sign(L.vps.sk, c.H(RID, C_VR, L.e))
        vr = ValidatedRequest(
            RID,
            C_VR,
            tx.b,
            tx.pos,
            tx.PID,
            bt.v,
            tx.e_i,
            L.e,
            R.sigma_R,
            h_proof,
            alpha,
            R,
            t_submit,
            h_st=h_st,
            v_RLI=L.checkpoints[tx.b].v_RLI,
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

    def round_ready(self, queued: int, oldest_wait: float, arrival_rate: float) -> bool:
        """Whether an authorization round starts now (queued validated requests, oldest wait in s)."""
        if self.variant == "per-request":
            return queued >= 1
        if self.variant == "fixed-batch":  # waits for its static size (no waiting bound)
            return queued >= self.fixed_B
        return queued >= self.target_batch_size(arrival_rate) or oldest_wait >= self.T_max_ms / 1000

    def select_round(self, queue, now: float, arrival_rate: float) -> list:
        """Phase 4 Step 1: the requests of the next round from queue = [(VR_i, ts_i^adm)] in admission order.
        CORA (full, cora-no-sfmr, re-zk, audit variants) or the arrival-order variants."""
        if self.variant == "per-request":
            return [queue[0][0]]
        if self.variant == "fixed-batch":
            return [vr for vr, _ in queue[: self.fixed_B]]
        cands = {vr.RID: (Candidate(vr.RID, vr.b, vr.pos, t), vr) for vr, t in queue}
        depth = len(self.L.batches[0].tree.levels) - 1
        chosen = cora_select(
            [c for c, _ in cands.values()],
            now=now,
            target=self.target_batch_size(arrival_rate),
            b_max=self.B_max,
            depth=depth,
            t_max=self.T_max_ms / 1000,
            w_ch=self.w_ch,
            w_f=self.w_f,
        )
        return [cands[c.rid][1] for c in chosen]

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
                ev = self.evidence[vr.RID]
                h_proof = c.H(ev["proof"])
                ok = h_proof == vr.h_proof and vr.C_VR == c.H(
                    vr.RID, self._hR(vr.req), vr.h_st, L.policies[vr.PID].C_P, h_proof, vr.e
                )
            if ok and self.variant == "re-zk":  # every participating member re-verifies the PQZK proof
                pol = L.policies[vr.PID]
                for _ in range(L.t):
                    ok = ok and c.zk_verify(vr.req.ID_r, ev["x"], ev["proof"], pol.threshold, vr.req.ts_r // 1000)
            t1 = time.perf_counter()
            bd["attest_ms"] += (t1 - t0) * 1000
            if not ok:
                continue
            fresh = self.state_digest(L.txs[vr.req.TID]) == vr.h_st and vr.e == L.e  # recomputed h_i^st
            bd["fresh_ms"] += (time.perf_counter() - t1) * 1000
            if fresh:
                eligible.append(vr)
        if not eligible:
            return None
        t2 = time.perf_counter()
        eligible.sort(key=lambda v: (v.b, v.pos, v.RID))  # canonical order (b_i, pos_i, RID_i)
        leaves = [c.HV("AUTH-LEAF", v.RID, v.C_VR, v.alpha) for v in eligible]  # eta_i
        tree = MerkleTree(leaves)
        c.counts["T_H"] += tree.hash_ops[0]
        gamma = self.plan_commitment(eligible)
        BID = os.urandom(16)
        ts = int(time.time())
        C_B = c.HV("AUTH-BATCH", BID, L.e, len(eligible), tree.root, gamma, ts)
        msg = C_B  # each approving member signs C_e^B
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
            gamma,
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

    def plan_commitment(self, members) -> bytes:
        """Gamma_e = H_V(CORA-PLAN || enc({(b_i, pos_i)})) over the canonically ordered authorized requests."""
        return self.c.HV("CORA-PLAN", *[x for v in members for x in (v.b, v.pos)])

    # ============================================================ Phase 5 (SFMR)
    def execute(self, auth: BatchAuth):
        L, c = self.L, self.c
        # Step 1: verify Auth_e^B (t committee approvals over C_e^B), the plan Gamma_e and every PBRP_i^auth
        if len({k for k, _ in auth.approvals}) < L.t or not all(
            c.verify(L.committee[k].pk, auth.C_B, sig) for k, sig in auth.approvals
        ):
            return []
        if self.plan_commitment(auth.members) != auth.gamma:  # positions changed after authorization: withheld
            return []
        authorized = {(v.b, v.pos) for v in auth.members}  # P^auth
        by_batch: dict[int, list] = {}
        for i, vr in enumerate(auth.members):
            c.counts["T_H"] += len(auth.proofs[vr.RID]) + 1
            if not verify_proof(auth.R_VR, auth.leaves[i], i, auth.proofs[vr.RID]):
                continue
            by_batch.setdefault(vr.b, []).append(vr)
        groups = {}
        for b, reqs in by_batch.items():
            bt = L.batches[b]
            seen, exe = set(), []
            for vr in reqs:  # conflicts: one resulting commitment per transaction per round
                tx = L.txs[vr.req.TID]
                if vr.req.TID in seen or bt.v != vr.v_b or (tx.b, tx.pos) not in authorized:  # P^exec in P^auth
                    continue
                if c.H(vr.req.m_new, vr.req.rho_new) != vr.req.D_new:
                    continue
                seen.add(vr.req.TID)
                exe.append(vr)
            if not exe:
                continue
            groups[b] = exe  # SFMR: every modification of batch b shares one root transition
        self.last_exec = {"batches": len(groups), "frontier": 0}
        if self.variant != "cora-no-sfmr":
            return self._apply(auth, groups)
        out = []  # No-SFMR: one independent Merkle update + PQCH adaptation per request, level by level
        for level in range(max((len(g) for g in groups.values()), default=0)):
            out += self._apply(auth, {b: [g[level]] for b, g in groups.items() if level < len(g)})
        return out

    def _apply(self, auth: BatchAuth, groups: dict):
        """SFMR + distributed PQCH adaptation + atomic finalization for {b: executable requests of batch b}:
        one root transition and one adaptation per batch; the combiner prepares (p_j, z_j) for every touched
        batch j, each of the t members returns S_k Z for the round, the combiner combines."""
        L, c = self.L, self.c
        prepared, finalized = [], []
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
                # SFMR: verify the old leaves against MR_b through the external frontier F_b, then update
                frontier = bt.tree.multiproof(sorted(old))
                self.last_exec["frontier"] += len(frontier)
                ok, ops = verify_multiproof(old_root, old, frontier, len(bt.tree.levels) - 1)
                c.counts["T_H"] += ops
                if not ok:
                    raise RuntimeError(f"BIMC multiproof failed for batch {b}")
                c.counts["T_H"] += bt.tree.update(changes)
                # Theta_b binds the SFMR root transition to the authorized execution; members check it (P_b in
                # Gamma_e, MR_b' the deterministic SFMR result) before releasing their PQCH shares
                theta = c.HV("SFMR-TRANS", auth.BID, b, bt.v, old_root, bt.tree.root, *sorted(changes), auth.gamma)
                jobs.append((b, grp, old_root, old_r, bt.tree.root, theta))
            R_old = np.stack([j[3] for j in jobs], axis=1)
            P, Z = c.ch_begin_adapt_many(L.pk_ch, [j[2] for j in jobs], R_old, [j[4] for j in jobs])
            deltas = [c.ch_part_adapt_many(L.td[k + 1], Z) for k in range(L.t)]
            R_new = c.ch_combine_many(P, Z, deltas)
            ok = c.ch_verify_many(L.pk_ch, [L.batches[j[0]].ch for j in jobs], [j[4] for j in jobs], R_new)
            for col, (b, grp, old_root, _, new_root, theta) in enumerate(jobs):
                if not ok[col]:
                    raise RuntimeError(f"PQCH adaptation failed for batch {b}")
                bt = L.batches[b]
                bt.r, bt.v = R_new[:, col].copy(), bt.v + 1
                prepared.append((b, grp, old_root, new_root, bt.v - 1, bt.v, bt.r, theta))
        for b, grp, old_root, new_root, v_old, v_new, new_r, theta in prepared:  # atomic finalization
            for vr in grp:
                tx = L.txs[vr.req.TID]
                D_old = tx.D
                tx.m, tx.rho, tx.D, tx.e_i = vr.req.m_new, vr.req.rho_new, vr.req.D_new, L.e
                L._index_put(tx)
                finalized.append((vr, tx, D_old, b, v_old, v_new, old_root, new_root, new_r, theta))
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
            mrs=[L.checkpoints[b].MR for b in touched],  # MR_b' of each transition, as the auditor reads it
            vbs=[L.checkpoints[b].v_b for b in touched],
            sigs=[L.checkpoints[b].sigma for b in touched],
        )
        self.pending_anchor.append(self.last_finalization)
        out = []
        xis = {}  # Xi_b = H_V(EXEC-EVIDENCE || Theta_b || CH_b || v_b' || R_RLI' || v_RLI'): one per batch transition
        for p in prepared:
            cp = L.checkpoints[p[0]]
            xis[p[0]] = c.HV("EXEC-EVIDENCE", p[7], cp.CH, cp.v_b, cp.R_RLI, cp.v_RLI)
        for vr, tx, D_old, b, v_old, v_new, old_root, new_root, new_r, theta in finalized:
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
                "theta": theta,
                "xi": xis[b],
                "positions": tuple(sorted(L.txs[v.req.TID].pos for v in groups[b])),  # P_b^exec
                "cp": L.checkpoints[b],  # the finalized A_b' of this transition
            }
            h_pbrp = self.pbrp_digest(vr.RID, auth.BID, tx.I, D_old, tx.D, b, tx.pos, v_old, v_new, theta, xis[b])
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
        cp = c.HV("RAI-CP", L.e, R, L.rai.snapshot, ts)  # CP_{e_A}^A
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
        rec_bytes = len(records) * (32 * 8 + L.c.sig.sig_size)  # per-record: eta, MP_B, C_VR, alpha, ...
        trans_bytes = 32 * 2 + 32 * 4  # Theta_b, Xi_b, (MR_b, MR_b', CH_b, r_b' digest)
        cp_bytes = 8 * 4 + 32 * 3 + L.c.sig.sig_size  # A_b' fields + sigma_b'
        if self.audit_mode == "per_record":  # Per-Record: individual paths + complete evidence for every record
            paths = sum(
                len(L.rai.shards[s].tree.proof(p)) + len(L.rai.global_tree.proof(s))
                for s, ps in by_shard.items()
                for p in ps
            )
            proof_bytes = 32 * paths
            auth_bytes = len(records) * (self._auth_bytes() + trans_bytes + cp_bytes)
        else:  # query-scoped multiproof + the SAVER DAG: each shared node once
            mp = {s: L.rai.shards[s].tree.multiproof(ps) for s, ps in by_shard.items()}
            gmp = L.rai.global_tree.multiproof(list(by_shard))
            proof_bytes = 32 * (sum(len(v) for v in mp.values()) + len(gmp))
            transitions = {(rr.b, rr.v_b_new) for rr in records}
            auth_bytes = len({rr.BID for rr in records}) * self._auth_bytes() + len(transitions) * (
                trans_bytes + cp_bytes
            )
        body = {"Q": Q, "records": records, "R_RAI": L.rai.root, "v_A": L.rai.snapshot}
        sigma = c.sign(L.audit_svc.sk, c.H(Q, len(records), L.rai.root, L.rai.snapshot))
        nbytes = entries_bytes + proof_bytes + auth_bytes + rec_bytes + L.c.sig.sig_size
        return AuditResponse(body, sigma, nbytes, records)

    def _auth_bytes(self):
        return 16 + 32 + 32 + 8 + 8 + self.L.t * (8 + self.c.sig.sig_size)

    def pbrp_digest(self, RID, BID, I, D, D_new, b, pos, v_b, v_b_new, theta, xi) -> bytes:
        """h_i^PBRP = H_V(PBRP || enc(PBRP_i)); Theta_b already binds (MR_b, MR_b', P_b, v_b, Gamma_e)."""
        return self.c.HV("PBRP", RID, BID, I, D, D_new, b, pos, v_b, v_b_new, theta, xi)

    def rai_entry(self, rr) -> bytes:
        tau = rr.pbrp["tau_A"]
        return self.c.H(tau, rr.RID, rr.BID, rr.PID, rr.e, rr.v_b, rr.v_b_new, rr.h_pbrp, rr.ts_red)

    def verify_audit(self, resp: AuditResponse, Q: bytes, deep=frozenset(), mode=None):
        """SAVER AuditVerify (Phase 6 Steps 4-6): returns {RID: accepted}, each record decided individually.

        Evidence nodes: request (per record), authorization (per BID), transition (per batch transition), checkpoint
        (per finalized A_b'). mode "saver" verifies each shared node once per state context chi(v) and records it in
        the verified-context store self.vcs, reused across audits; "shared" (Shared-Evidence variant) and
        "per_record" (Per-Record variant) re-verify the shared nodes for every dependent record. deep: True (every
        record), falsy (routine) or a set of RIDs escalated to independent PQZK verification.
        self.last_breakdown (ms) and self.last_nodes (cryptographically verified nodes per type) describe the call."""
        L, c = self.L, self.c
        mode = mode or self.audit_mode
        body = resp.body
        deep = {rr.RID for rr in resp.records} if deep is True else set(deep or ())
        bd = dict.fromkeys(("response_ms", "rai_mp_ms", "committee_ms", "attest_ms", "state_ms", "cp_ms", "zk_ms"), 0.0)
        nodes = dict.fromkeys(("req", "auth", "trans", "cp", "zk"), 0)
        self.last_breakdown, self.last_nodes = bd, nodes
        t0 = time.perf_counter()
        e, R_cp, v_cp, ts_cp, cp_A = self.rai_checkpoint
        # the selected RAI checkpoint is the one ANCHORED on the PBN, read from the chain
        ok_resp = (
            body["Q"] == Q
            and L.anchor.read("rai_checkpoint", epoch=e) == cp_A
            and (body["R_RAI"], body["v_A"]) == (R_cp, v_cp)
            and c.HV("RAI-CP", e, R_cp, v_cp, ts_cp) == cp_A
            and c.verify(L.audit_svc.pk, c.H(body["Q"], len(body["records"]), body["R_RAI"], body["v_A"]), resp.sigma)
        )
        bd["response_ms"] = (time.perf_counter() - t0) * 1000
        if not ok_resp:
            return {rr.RID: False for rr in resp.records}
        t0 = time.perf_counter()  # RAI multiproof (hash-based)
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
        t0 = time.perf_counter()  # finalized checkpoint references (b, v_b') -> MR_b' as anchored: one read
        anchored = L.anchor.read("checkpoint_history", keys={(rr.pbrp["b"], rr.v_b_new) for rr in resp.records})
        bd["state_ms"] += (time.perf_counter() - t0) * 1000

        def node(kind, chi, verify):
            if mode == "saver" and chi in self.vcs:  # Reuse(v, chi) = 1 iff chi = chi(v) and VCS[chi(v)] = valid
                return True
            nodes[kind] += 1
            ok = verify()
            if ok and mode == "saver":
                self.vcs.add(chi)
            return ok

        result = {}
        for rr in resp.records:
            p, vr = rr.pbrp, rr.pbrp["vr"]
            auth, cp = self.auths[rr.BID], rr.pbrp["cp"]
            t0 = time.perf_counter()
            chi_auth = c.HV(
                "VERIFY-CTX", "auth", auth.C_B, auth.R_VR, *[s for _, s in auth.approvals], rr.BID, auth.gamma, auth.e
            )
            ok = node("auth", chi_auth, lambda auth=auth: self._verify_auth_node(auth))
            t1 = time.perf_counter()
            nodes["req"] += 1  # request node: q * C_req, always verified
            ok &= c.HV("AUTH-LEAF", vr.RID, vr.C_VR, vr.alpha) == p["eta"]
            ok &= verify_proof(auth.R_VR, p["eta"], auth.members.index(vr), p["MP_B"])
            c.counts["T_H"] += len(p["MP_B"]) + 1
            ok &= c.verify(L.vps.pk, c.H(vr.RID, vr.C_VR, vr.e), vr.alpha)  # routine: the VPS decision alpha_i
            t2 = time.perf_counter()
            c.counts["T_H"] += 2  # L_i, L_i' recomputation (request-specific)
            # chi(v) hashes the node's complete evidence and its state context: any change verifies afresh
            chi_tr = c.HV(
                "VERIFY-CTX",
                "trans",
                p["theta"],
                p["xi"],
                p["b"],
                rr.v_b,
                rr.v_b_new,
                p["MR"],
                p["MR_new"],
                _raw(p["CH"]),
                _raw(p["r_new"]),
                *p["positions"],
                auth.gamma,
            )
            ok &= node("trans", chi_tr, lambda rr=rr, auth=auth: self._verify_transition_node(rr, auth))
            t3 = time.perf_counter()
            mr_chain = anchored.get((p["b"], rr.v_b_new))  # MR_b' as anchored on the PBN, read in THIS audit
            chi_cp = c.HV("VERIFY-CTX", "cp", cp.b, cp.MR, cp.v_b, cp.sigma, cp.v_RLI, mr_chain, v_cp, cp_A)
            ok &= node("cp", chi_cp, lambda rr=rr, mr_chain=mr_chain: self._verify_checkpoint_node(rr, mr_chain))
            t4 = time.perf_counter()
            if rr.RID in deep:  # dependency-selective escalation: x_i, pi_i^PQ for this request only
                nodes["zk"] += 1
                ev = self.evidence[rr.RID]
                ok &= (
                    c.zk_verify(vr.req.ID_r, ev["x"], ev["proof"], L.policies[vr.PID].threshold, vr.req.ts_r // 1000)
                    and c.H(ev["proof"]) == vr.h_proof
                )
            t5 = time.perf_counter()
            # h_PBRP binds the returned transition (catches modified D_i' / substituted evidence) and the record
            # must reproduce its authenticated RAI entry (catches modified / stale fields)
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
                    p["theta"],
                    p["xi"],
                )
                == rr.h_pbrp
            )
            tau = p["tau_A"]
            ok &= self.rai_entry(rr) == L.rai.shards[L.rai.sid(tau)].entries[tau]
            bd["committee_ms"] += (t1 - t0) * 1000
            bd["attest_ms"] += (t2 - t1) * 1000
            bd["state_ms"] += (t3 - t2) * 1000
            bd["cp_ms"] += (t4 - t3) * 1000
            bd["zk_ms"] += (t5 - t4) * 1000
            result[rr.RID] = bool(ok)
        return result

    def _verify_auth_node(self, auth) -> bool:
        """C_e^B reconstructed from (BID, e, m, R_VR, Gamma_e, ts) and >= t distinct committee approvals on it."""
        L, c = self.L, self.c
        C_B = c.HV("AUTH-BATCH", auth.BID, auth.e, len(auth.members), auth.R_VR, auth.gamma, auth.ts)
        return (
            C_B == auth.C_B
            and len({k for k, _ in auth.approvals}) >= L.t
            and all(c.verify(L.committee[k].pk, auth.C_B, s) for k, s in auth.approvals)
        )

    def _verify_transition_node(self, rr, auth) -> bool:
        """P_b^exec in P_b^auth, Theta_b and Xi_b bindings, PQCH preservation."""
        L, c = self.L, self.c
        p = rr.pbrp
        cp = p["cp"]
        authorized = {v.pos for v in auth.members if v.b == p["b"]}
        theta = c.HV("SFMR-TRANS", rr.BID, p["b"], rr.v_b, p["MR"], p["MR_new"], *p["positions"], auth.gamma)
        xi = c.HV("EXEC-EVIDENCE", theta, cp.CH, cp.v_b, cp.R_RLI, cp.v_RLI)
        return (
            set(p["positions"]) <= authorized
            and theta == p["theta"]
            and xi == p["xi"]
            and c.ch_verify(L.pk_ch, p["CH"], p["MR_new"], p["r_new"])  # r_b' as recorded in A_b'
        )

    def _verify_checkpoint_node(self, rr, mr_chain) -> bool:
        """The checkpoint authority's PQ signature on the finalized A_b' and its MR_b' as anchored on the PBN."""
        L, c = self.L, self.c
        cp, p = rr.pbrp["cp"], rr.pbrp
        msg = c.H(cp.b, cp.CH, cp.MR, cp.r.tobytes(), cp.R_RLI, cp.v_RLI, cp.e, cp.v_b, cp.ts)
        return cp.MR == p["MR_new"] == mr_chain and cp.v_b == rr.v_b_new and c.verify(L.cp.pk, msg, cp.sigma)


def _raw(x) -> bytes:
    """Exact byte image of a PQCH value or randomness (numpy array) for use as a dictionary key."""
    return x.tobytes() if hasattr(x, "tobytes") else repr(x).encode()
