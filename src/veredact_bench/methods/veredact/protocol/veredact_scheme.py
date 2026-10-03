"""VeRedact-PQ behind the shared Scheme contract.

Boundaries (docs/experiments.md):
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

    def __init__(self, cfg: dict, committee_n: int | None = None, committee_t: int | None = None):
        self.cfg = cfg
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
        # per request at the VPS: requester ML-DSA verify + STARK verify + attestation and admission-receipt
        # signatures; Phase 4 adds (1 attestation verify) per request and t signatures + t verifications per BATCH.
        return AuthCost(
            signature_verifications=2,
            proof_verifications=1,
            signatures_generated=2,
            consensus_blocks=0,
            round_trips=0,
        )

    # ------------------------------------------------------------------ setup (untimed)
    def setup(self, dataset: Dataset) -> None:
        self.crypto = Crypto(self.cfg, dataset.requesters)
        self.anchor = make_anchor(self.cfg)
        self.ledger = Ledger(self.cfg, self.crypto, self.anchor, self.n, self.t)
        self.ledger.commit_transactions(dataset.transactions)
        self.p = VeRedactPQ(self.ledger, self.cfg)
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
        return batch_auth, (time.perf_counter() - t0) * 1000

    # ------------------------------------------------------------------ Phase 5
    def redact(self, batch: list, batch_auth=None) -> RedactionResult:
        t0 = time.perf_counter()
        if batch_auth is None:
            batch_auth = self.p.authorize([a.handle for a in batch if a.ok])
        before = self.crypto.counts["T_CB"]
        records = self.p.execute(batch_auth) if batch_auth else []
        crypto_ms = (time.perf_counter() - t0) * 1000
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

    def audit(self, query: AuditQuery) -> AuditResult:
        recs = self.p.records[: query.records]
        rng = random.Random(self.cfg["meta"]["seed"])
        if query.tamper:  # Exp. 4 fault injection on copies of the returned records
            recs = [self._tamper(r, query.tamper.get(i), rng) for i, r in enumerate(recs)]
        Q, sigma_Q = self.p.make_query("authorization+state", len(recs))  # auditor signs Q_j^A (untimed)
        t0 = time.perf_counter()
        resp = self.p.audit(recs, Q, sigma_Q)
        t1 = time.perf_counter()
        accepted = self.p.verify_audit(resp, Q, deep=query.deep)
        t2 = time.perf_counter()
        return AuditResult(
            "redaction provenance (authorization + state transition)",
            (t1 - t0) * 1000,
            (t2 - t1) * 1000,
            resp.nbytes,
            {i: accepted[r.RID] for i, r in enumerate(recs)},
            dict(self.p.last_breakdown),
        )

    def _tamper(self, rr, kind, rng):
        if not kind:
            return rr
        import copy

        from ..crypto.hashing import H

        r = copy.copy(rr)
        if kind == "modified":
            r.D_new = H("forged", r.D_new)
        elif kind == "substituted":
            r.h_pbrp = H("substituted", r.h_pbrp)
        elif kind == "stale":
            r.v_b_new -= 1
        return r

    def teardown(self) -> None:
        for f in self.p.pending_anchor:
            f.result()
        self.anchor.close()
