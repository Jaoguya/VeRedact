"""S27 [27] ETCH behind the shared Scheme contract (docs/baselines/S27-etch.md).

Paper workflow, per request (Sec. VI):
  authorize  target lookup only. The paper has no request object and no approval protocol: redactors
             "reach a consensus" by means it leaves unspecified, and the t-of-n threshold is enforced only
             inside Adapt. No policy, no requester privacy — the paper defines none.
  redact     ETCH.Adapt (2 CA rounds, t shares) -> new (r, w); nodes re-verify ETCH hash + initiator
             signature; one ledger write per redaction (no batching in the paper).
  audit      not defined by the paper -> NotSupported (capability column says so; nothing synthesised).
Instantiation: the paper's own (secp256k1, SHA-256), classical.
"""
import time

from veredact_bench.methods.baselines.s27_etch.construction import Initiator, keygen, redact_tx, verify_tx

from veredact_bench.evaluation.anchor import gather, make_anchor
from veredact_bench.methods.scheme import (AuthCost, Authorization, Capabilities, Dataset, RedactionOutcome,
                                   RedactionResult, RedactionRequest, Scheme)


class ETCHScheme(Scheme):
    key = "S27"

    def __init__(self, cfg: dict, redactors_n: int | None = None, threshold_t: int | None = None):
        b = cfg["baselines"]["S27"]
        self.cfg, self.n, self.t = cfg, redactors_n or b["redactors_n"], threshold_t or b["threshold_t"]

    def capabilities(self) -> Capabilities:
        return Capabilities(pq_security=False, distributed_auth=True, policy_control=False, batch_redaction=False,
                            private_verification=False, verifiable_auditing=False, state_freshness_check=False,
                            consensus_bound_auth=False)

    def auth_cost(self) -> AuthCost:
        return AuthCost()  # no approval step in the paper: the threshold lives in Adapt (redact)

    def setup(self, dataset: Dataset) -> None:
        self.keys = keygen(self.t, self.n)  # Pedersen/Feldman DKG among redactors
        self.initiators = [Initiator() for _ in range(dataset.requesters)]
        self.txs = {tx.tid: (self.initiators[tx.owner].create_tx(self.keys.Y, tx.payload), tx.owner)
                    for tx in dataset.transactions}
        self.anchor = make_anchor(self.cfg)
        self.signers = list(self.keys.parts)[: self.t]

    def authorize(self, req: RedactionRequest) -> Authorization:
        t0 = time.perf_counter()
        entry = self.txs.get(req.tid)
        if entry is None or req.fault == "absent":
            return Authorization(req, False, (time.perf_counter() - t0) * 1000, reason="nonexistent target")
        return Authorization(req, True, (time.perf_counter() - t0) * 1000)

    def redact(self, batch: list) -> RedactionResult:
        crypto_ms, outcomes, adapt, futs = 0.0, [], 0, []
        for a in batch:  # the paper redacts one transaction at a time
            if not a.ok:
                outcomes.append(RedactionOutcome(a.request.seq, False, reason=a.reason))
                continue
            t0 = time.perf_counter()
            tx, owner = self.txs[a.request.tid]
            new_tx = redact_tx(self.keys, self.signers, tx, a.request.new_payload)
            ok = verify_tx(self.keys.Y, self.initiators[owner].sk.public_key, new_tx)
            crypto_ms += (time.perf_counter() - t0) * 1000
            adapt += 1
            if ok:
                self.txs[a.request.tid] = (new_tx, owner)
                # pipelined like VeRedact's anchoring: finality is tracked by the Future, not awaited here
                futs.append(self.anchor.submit("baseline_redaction", tid=a.request.tid.ljust(32, b"\0")[:32],
                                               commit=new_tx.etch.r.format()[1:], version=1,
                                               evidence=new_tx.etch.w.to_bytes(32, "big")))
            outcomes.append(RedactionOutcome(a.request.seq, ok, reason="" if ok else "adapt verify"))
        return RedactionResult(outcomes, crypto_ms, 0.0, adapt, finality=gather(futs) if futs else None,
                               finality_op="baseline_redaction")

    def teardown(self) -> None:
        self.anchor.close()
