"""VeRedact-PQ behind the shared Scheme contract.

Boundaries (Other/docs/experiments.md):
  authorize(req)   Phase 3 at the VPS: admission, SA-RLI resolution, ML-DSA verify, public policy,
                   STARK verify, attestation. Requester-side signing/proving happens BEFORE the timer.
  authorize_batch  Phase 4: attestation + freshness checks, R_e^VR, C_e^B, t committee ML-DSA signatures.
  redact(batch)    Phase 4 (if not done) + Phase 5: RADC transition, BIMC update, distributed SIS-PQCH
                   adaptation, checkpoints; ledger finality returned as a Future (crypto/ledger split).
  audit(query)     Phase 6: RAI multiproof + shared batch evidence (service), AuditVerify (auditor).
"""

import random
import time

from veredact_bench.evaluation.anchor import make_anchor
from veredact_bench.methods.scheme import (
    AuditQuery,
    AuditResult,
    AuthCost,
    Authorization,
    Capabilities,
    Dataset,
    RedactionOutcome,
    RedactionRequest,
    RedactionResult,
    Scheme,
)

from ..crypto import Crypto
from .ledger import Ledger
from .veredact import Rejection, VeRedactPQ


class VeRedactScheme(Scheme):
    key = "veredact"

    def __init__(self, cfg: dict, committee_n: int | None = None, committee_t: int | None = None, variant="full"):
        self.cfg = cfg
        self.variant = variant
        self.n = committee_n or cfg["veredact"]["committee_n"]
        self.t = committee_t or cfg["veredact"]["committee_t"]
        self._last_submitted = None

    def capabilities(self) -> Capabilities:
        return Capabilities(
            pq_security=True,
            distributed_auth=True,
            policy_control=True,
            batch_redaction=True,
            private_verification=True,
            verifiable_auditing=True,
            state_freshness_check=True,
            consensus_bound_auth=False,
        )

    def auth_cost(self) -> AuthCost:
        # per request at the VPS: requester ML-DSA verify + STARK verify; BatchAttest signs one window root per
        # vps_window admissions (the attestation is also the receipt), so per request it rounds to 0 for W > 1.
        # Phase 4 adds the attestation check (one window verify per distinct window + a path) per request and t
        # signatures + t verifications per BATCH.
        W = int(self.cfg["veredact"].get("vps_window", 1))
        return AuthCost(
            signature_verifications=2,
            proof_verifications=1,
            signatures_generated=1 if W == 1 else 0,
            consensus_blocks=0,
            round_trips=0,
        )

    # ------------------------------------------------------------------ setup (untimed)
    def setup(self, dataset: Dataset) -> None:
        self.crypto = Crypto(self.cfg, dataset.requesters)
        self.anchor = make_anchor(self.cfg)
        self.ledger = Ledger(self.cfg, self.crypto, self.anchor, self.n, self.t)
        self.ledger.commit_transactions(dataset.transactions)
        self.p = VeRedactPQ(self.ledger, self.cfg, self.variant)
        self.committee = self.p.committee
        self.last_auth_net_ms = 0.0  # committee message delay of the last authorize_batch
        self.crypto.reset()

    def prepare(self, req: RedactionRequest):
        """Requester side (client): sign R_i and prove policy compliance against the CURRENT state."""
        tid = req.tid if req.fault != "absent" else b"TX-DOES-NOT-EXIST"
        R = self.p.make_request(
            req.requester % len(self.ledger.requesters),
            tid,
            req.new_payload,
            tamper=req.fault if req.fault in ("sig", "zk", "policy", "stale") else "",
        )
        if req.fault == "replay" and self._last_submitted is not None:
            return self._last_submitted  # re-send an already submitted request (same nonce)
        self._last_submitted = R
        return R

    def prepare_begin(self, req: RedactionRequest):
        """Exp. 1 split of prepare (audit A3): (R_i bound to the CURRENT batch version, job for the expensive
        requester work, or None when nothing is left to do — a replay re-sends the last request)."""
        if req.fault == "replay" and self._last_submitted is not None:
            return self._last_submitted, None
        tid = req.tid if req.fault != "absent" else b"TX-DOES-NOT-EXIST"
        R, job = self.p.request_skeleton(
            req.requester % len(self.ledger.requesters),
            tid,
            req.new_payload,
            tamper=req.fault if req.fault in ("sig", "zk", "policy", "stale") else "",
        )
        self._last_submitted = R
        return R, job

    # ------------------------------------------------------------------ Phase 3
    def authorize(self, req: RedactionRequest, prepared=None) -> Authorization:
        R = prepared if prepared is not None else self.prepare(req)
        t0 = time.perf_counter()
        vr = self.p.validate(R)
        ms = (time.perf_counter() - t0) * 1000
        if isinstance(vr, Rejection):
            return Authorization(req, False, ms, reason=f"{vr.stage}:{vr.reason}")
        return Authorization(req, True, ms, handle=vr)

    # ------------------------------------------------------------------ Phase 4
    def authorize_batch(self, auths: list):
        t0 = time.perf_counter()
        batch_auth = self.p.authorize([a.handle for a in auths if a.ok])
        credit_s, self.last_auth_net_ms = self.committee.take()  # slowest member only; delay is not crypto
        ph4_ms = (time.perf_counter() - t0 - credit_s) * 1000
        self.p.flush_anchors()  # ledger work, outside the Phase 4 crypto timer (rule 6)
        return batch_auth, ph4_ms

    # ------------------------------------------------------------------ Phase 5
    def redact(self, batch: list, batch_auth=None) -> RedactionResult:
        t0 = time.perf_counter()
        if batch_auth is None:
            batch_auth = self.p.authorize([a.handle for a in batch if a.ok])
        before = self.crypto.counts["T_CB"]
        records = self.p.execute(batch_auth) if batch_auth else []
        credit_s, net_ms = self.committee.take()  # slowest committee member only; message delay is not crypto
        crypto_ms = (time.perf_counter() - t0 - credit_s) * 1000
        self.p.flush_anchors()  # ledger work, outside the Phase 4/5 crypto timer (rule 6)
        done = {rr.RID for rr in records}
        outcomes = []
        for a in batch:
            ok = a.ok and a.handle is not None and a.handle.RID in done
            outcomes.append(
                RedactionOutcome(
                    a.request.seq,
                    ok,
                    stale=a.ok and not ok,
                    reason="" if ok else ("stale/conflict" if a.ok else a.reason),
                )
            )
        return RedactionResult(
            outcomes,
            crypto_ms,
            0.0,
            self.crypto.counts["T_CB"] - before,
            finality=self.p.last_finalization if records else None,
            net_ms=net_ms,
        )

    # ------------------------------------------------------------------ Phase 6
    def index_records(self):
        self.p.index_records()
        self.p.pending_anchor[-1].result()  # CP_e^A mined before any audit reads it from the chain (untimed)

    def audit(self, query: AuditQuery) -> AuditResult:
        recs = self.p.records[: query.records]
        rng = random.Random(self.cfg["meta"]["seed"])
        applied, restore = dict(query.tamper), []
        if query.tamper:  # Exp. 4 fault injection on copies of the returned records
            self._tamper_store(recs, query.tamper, applied, restore)
            recs = [self._tamper(r, query.tamper.get(i), rng, applied, i) for i, r in enumerate(recs)]
        Q, sigma_Q = self.p.make_query("authorization+state", len(recs))  # auditor signs Q_j^A (untimed)
        # d_Q requests escalated to PQZK verification (seeded); deep = every request
        k = round(query.deep_fraction * len(recs))
        deep = True if query.deep else {r.RID for r in random.Random(self.cfg["meta"]["seed"] + 1).sample(recs, k)}
        self.p.vcs.clear()  # one fresh auditor per query: SAVER reuse is measured within the query
        try:
            t0 = time.perf_counter()
            resp = self.p.audit(recs, Q, sigma_Q)
            t1 = time.perf_counter()
            accepted = self.p.verify_audit(resp, Q, deep=deep)
            t2 = time.perf_counter()
        finally:
            for store, k, genuine in restore:  # the auditor's evidence stores back to the genuine entries
                store[k] = genuine
        bd = dict(self.p.last_breakdown)
        return AuditResult(
            "redaction provenance (authorization + state transition)",
            (t1 - t0) * 1000,
            (t2 - t1) * 1000,
            resp.nbytes,
            {i: accepted[r.RID] for i, r in enumerate(recs)},
            bd,
            dict(self.p.last_nodes),
            read_ms=bd.pop("read_ms", 0.0),
            tampered=applied if query.tamper else None,
        )

    def _tamper_store(self, recs, tamper, applied, restore):
        """Exp. 4 faults on evidence the auditor resolves by id instead of reading it from the record (untimed;
        audit() puts the genuine entries back).
        forged_approval: one committee approval of the record's authorization batch is a valid signature by a key
            outside the committee. The authorization node is shared, so every returned record of that batch
            depends on forged evidence: all of them count as tampered.
        forged_proof: another request's genuine PQZK proof stands in for this request's. Routine verification
            never opens the proof; only a record escalated to PQZK verification (d_Q) can reject it."""
        import dataclasses

        p = self.p
        bids = {recs[i].BID for i, k in tamper.items() if k == "forged_approval"}
        for bid in bids:
            auth = p.auths[bid]
            k0, _ = auth.approvals[0]
            forged = [(k0, p.c.sign(p.L.audit_svc.sk, auth.C_B)), *auth.approvals[1:]]
            restore.append((p.auths, bid, auth))
            p.auths[bid] = dataclasses.replace(auth, approvals=forged)
        if bids:
            applied.update({i: "forged_approval" for i, r in enumerate(recs) if r.BID in bids})
        swaps = {}  # chosen on the genuine store first, so no record gets its own proof back through a chain
        for i, k in tamper.items():
            if k == "forged_proof":
                rid = recs[i].RID
                other = next((o.RID for o in p.records if o.RID != rid), None)
                if other is None:
                    raise ValueError("forged_proof needs a second record in the history")
                swaps[rid] = p.evidence[other]["proof"]
        for rid, proof in swaps.items():
            restore.append((p.evidence, rid, p.evidence[rid]))
            p.evidence[rid] = dict(p.evidence[rid], proof=proof)

    def _tamper(self, rr, kind, rng, applied, i):
        if kind in (None, "", "forged_approval", "forged_proof"):  # store faults: see _tamper_store
            return rr
        import copy

        from ..crypto.hashing import H

        r = copy.copy(rr)
        r.pbrp = dict(rr.pbrp)
        if kind == "modified":  # a committed field altered
            r.D_new = H("forged", r.D_new)
        elif kind == "substituted":
            # #8 change 3: GENUINE evidence of another redaction (preferably another authorization batch) inserted
            # under this record; only its context binding (h_i^PBRP in the RAI entry, chi(v)) can catch it
            others = [o for o in self.p.records if o.RID != rr.RID]
            other = next((o for o in others if o.BID != rr.BID), others[0] if others else None)
            if other is None:
                raise ValueError("substituted evidence needs a second record in the history")
            r.pbrp = dict(other.pbrp, tau_A=rr.pbrp["tau_A"])  # still resolves to this record's RAI entry
        elif kind == "stale":
            # #8 change 3: a GENUINE earlier transition and checkpoint of the same batch replayed (anchored on the
            # chain and correctly signed); the batch's most recent earlier version
            b = rr.pbrp["b"]
            older = [o for o in self.p.records if o.pbrp["b"] == b and o.v_b_new < rr.v_b_new]
            if older:
                old = max(older, key=lambda o: o.v_b_new)
                for k in ("v_b", "v_b_new", "MR", "MR_new", "r", "r_new", "theta", "xi", "positions", "cp"):
                    r.pbrp[k] = old.pbrp[k]
                r.v_b, r.v_b_new = old.v_b, old.v_b_new
            else:  # the batch has no earlier transition in this history: an older version number is claimed,
                r.v_b_new -= 1  # a different and easier fault, so it is counted apart (stale_version)
                applied[i] = "stale_version"
        return r

    def set_variant(self, variant: str) -> None:
        """Switch an audit-only variant onto an existing history (shared-evidence / per-record differ from
        VeRedact-PQ only in Phase 6, so they audit the history VeRedact-PQ built)."""
        self.variant = self.p.variant = variant
        self.p.audit_mode = {"shared-evidence": "shared", "per-record": "per_record"}.get(variant, "saver")

    def teardown(self) -> None:
        for f in self.p.pending_anchor:
            f.result()
        self.anchor.close()
