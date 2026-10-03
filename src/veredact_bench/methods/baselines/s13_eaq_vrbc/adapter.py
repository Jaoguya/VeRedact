"""S13 [13] EAQ-VRBC behind the shared Scheme contract (docs/baselines/S13-eaq-vrbc.md).

Paper workflow:
  authorize  NO per-request protocol: redaction authority is the System Manager's trapdoor possession.
             We measure exactly that key-possession check and synthesise nothing (Exp. 2: lower bound).
  redact     per request (block-level CH): Redaction + Update — check the old tag, double-trapdoor CH
             collision for the block, Auditee CH verification, new identity-based tag and its check,
             revoke the old tag in the RSA accumulator; one ledger write.
  audit      Audit phase: challenge over the queried blocks -> aggregated tags + aggregated
             non-membership witness (Alg. 2, NI-SimPoE) -> AuditVerify (Alg. 3). The protocol answers
             "are these blocks intact and current?" for the challenged set as a whole: one decision,
             applied to every record of the query (it cannot reject records individually).
"""
import os
import time

from veredact_bench.methods.baselines.s13_eaq_vrbc.construction import Ledger, setup as s13_setup

from veredact_bench.evaluation.anchor import gather, make_anchor
from veredact_bench.methods.scheme import (AuditQuery, AuditResult, AuthCost, Authorization, Capabilities, Dataset,
                                   RedactionOutcome, RedactionResult, RedactionRequest, Scheme)


class EAQVRBCScheme(Scheme):
    key = "S13"

    def __init__(self, cfg: dict):
        self.cfg, self.b = cfg, cfg["baselines"]["S13"]

    def capabilities(self) -> Capabilities:
        return Capabilities(pq_security=False, distributed_auth=False, policy_control=False, batch_redaction=False,
                            private_verification=False, verifiable_auditing=True, state_freshness_check=True,
                            consensus_bound_auth=False)

    def auth_cost(self) -> AuthCost:
        return AuthCost()  # key-possession check only: no signature/proof verification, no network

    def setup(self, dataset: Dataset) -> None:
        self.p = s13_setup(self.b["rsa_bits"], self.b["miners"], self.b["l_bits"])
        self.L = Ledger(self.p)
        N = self.cfg["dataset"]["leaves_per_batch"]
        self.block_of, self.txs = {}, {}
        for off in range(0, len(dataset.transactions), N):
            chunk = dataset.transactions[off:off + N]
            b = self.L.upload([t.payload for t in chunk])
            for pos, t in enumerate(chunk):
                self.block_of[t.tid] = (b.idx, pos)
        self.anchor = make_anchor(self.cfg)
        self.redacted = []  # (seq, block) in redaction order, for audit queries

    def authorize(self, req: RedactionRequest) -> Authorization:
        t0 = time.perf_counter()
        ok = req.tid in self.block_of and req.fault != "absent" and self.p.x is not None  # SM holds TK
        return Authorization(req, ok, (time.perf_counter() - t0) * 1000, reason="" if ok else "nonexistent target")

    def redact(self, batch: list) -> RedactionResult:
        crypto_ms, outcomes, futs = 0.0, [], []
        for a in batch:
            if not a.ok:
                outcomes.append(RedactionOutcome(a.request.seq, False, reason=a.reason))
                continue
            s, pos = self.block_of[a.request.tid]
            t0 = time.perf_counter()
            txs = list(self.L.txs[s])
            txs[pos] = a.request.new_payload
            ok = self.L.redact(s, txs)  # old-tag check, CH collision + verify, new tag + check, revocation
            crypto_ms += (time.perf_counter() - t0) * 1000
            if not ok:
                outcomes.append(RedactionOutcome(a.request.seq, False, reason="tag/CH check failed"))
                continue
            tag = self.L.tags[s][0].S.to_bytes(self.p.N.bit_length() // 8 + 1, "big")
            # pipelined like VeRedact's anchoring: finality is tracked by the Future, not awaited here
            futs.append(self.anchor.submit("baseline_redaction", tid=a.request.tid.ljust(32, b"\0")[:32],
                                           commit=self.L.blocks[s].m[:32], version=len(self.L.acc.revoked),
                                           evidence=tag))
            self.redacted.append((a.request.seq, s))
            outcomes.append(RedactionOutcome(a.request.seq, True))
        return RedactionResult(outcomes, crypto_ms, 0.0, len(futs), finality=gather(futs) if futs else None,
                               finality_op="baseline_redaction")

    def audit(self, query: AuditQuery) -> AuditResult:
        blocks = sorted({s for _, s in self.redacted[: query.records]})
        chal = [(i, int.from_bytes(os.urandom(8), "big") + 1) for i in blocks]
        saved = {}
        for s in {self.redacted[idx][1] for idx in query.tamper}:  # Exp. 4: corrupt each tampered block's tag ONCE
            saved[s] = self.L.tags[s]  # (two records in one block must not flip the same bit back)
            t, c, hh = self.L.tags[s]
            self.L.tags[s] = (type(t)(t.S ^ 1, t.v), c, hh)
        t0 = time.perf_counter()
        proof = self.L.audit_prove(chal)
        t1 = time.perf_counter()
        ok = self.L.audit_verify(chal, proof)
        t2 = time.perf_counter()
        self.L.tags.update(saved)
        (V, S), mu, w = proof
        nbytes = 2 * (self.p.N.bit_length() // 8) + (mu.bit_length() + 7) // 8 + \
            sum((x.bit_length() + 7) // 8 for x in (w.a, w.B, w.C, w.D, w.pi_C, w.pi_D)) + 16 * len(w.xs)
        return AuditResult("ledger integrity + version freshness (aggregate, per challenged set)",
                           (t1 - t0) * 1000, (t2 - t1) * 1000, nbytes,
                           {i: ok for i in range(min(query.records, len(self.redacted)))})

    def teardown(self) -> None:
        self.anchor.close()
