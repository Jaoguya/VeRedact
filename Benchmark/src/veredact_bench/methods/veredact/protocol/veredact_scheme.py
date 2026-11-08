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
        ph4_ms = (time.perf_counter() - t0) * 1000
        self.p.flush_anchors()  # ledger work, outside the Phase 4 crypto timer (rule 6)
        return batch_auth, ph4_ms

    # ------------------------------------------------------------------ Phase 5
    def redact(self, batch: list, batch_auth=None) -> RedactionResult:
        t0 = time.perf_counter()
        if batch_auth is None:
            batch_auth = self.p.authorize([a.handle for a in batch if a.ok])
        before = self.crypto.counts["T_CB"]
        records = self.p.execute(batch_auth) if batch_auth else []
        crypto_ms = (time.perf_counter() - t0) * 1000
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
        )

    # ------------------------------------------------------------------ Phase 6
    def index_records(self):
        self.p.index_records()
        self.p.pending_anchor[-1].result()  # CP_e^A mined before any audit reads it from the chain (untimed)

    def audit(self, query: AuditQuery) -> AuditResult:
        recs = self.p.records[: query.records]
        rng = random.Random(self.cfg["meta"]["seed"])
        if query.tamper:  # Exp. 4 fault injection on copies of the returned records
            recs = [self._tamper(r, query.tamper.get(i), rng) for i, r in enumerate(recs)]
        Q, sigma_Q = self.p.make_query("authorization+state", len(recs))  # auditor signs Q_j^A (untimed)
        # d_Q requests escalated to PQZK verification (seeded); deep = every request
        k = round(query.deep_fraction * len(recs))
        deep = True if query.deep else {r.RID for r in random.Random(self.cfg["meta"]["seed"] + 1).sample(recs, k)}
        self.p.vcs.clear()  # one fresh auditor per query: SAVER reuse is measured within the query
        t0 = time.perf_counter()
        resp = self.p.audit(recs, Q, sigma_Q)
        t1 = time.perf_counter()
        accepted = self.p.verify_audit(resp, Q, deep=deep)
        t2 = time.perf_counter()
        return AuditResult(
            "redaction provenance (authorization + state transition)",
            (t1 - t0) * 1000,
            (t2 - t1) * 1000,
            resp.nbytes,
            {i: accepted[r.RID] for i, r in enumerate(recs)},
            dict(self.p.last_breakdown),
            dict(self.p.last_nodes),
        )

    def _tamper(self, rr, kind, rng):
        if not kind:
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
            else:  # the batch has no earlier transition in this history: an older version number is claimed
                r.v_b_new -= 1
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
