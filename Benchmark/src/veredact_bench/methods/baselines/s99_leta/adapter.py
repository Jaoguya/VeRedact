"""S99 LETA behind the shared Scheme contract (Other/docs/baselines/S99-leta.md).

LETA is a batch AUTHENTICATION scheme, not a redactable blockchain: it is compared only where VeRedact-PQ
authenticates a batch of requests (Exp. 2, Phase 4) and at the primitive level (Exp. 0, incl. its ZKP).
Mapping (paper Sec. IV, one requester = one vehicle, one authorization batch = one platoon):
  prepare     the vehicle signs its request m = H(tid || new payload): Sign_Vi = (r, c), Z_Vi = (mu, r, c)
              (Eqs. 6-8). Requester side: untimed in Exp. 2, like VeRedact-PQ's sign + prove.
  authorize   the PL's per-vehicle identity check M'_{i,2} = h0(M_{i,1} || T3) == M_{i,2} (Sec. IV-B4c).
  authorize_batch
              PL: VPD-Tree over the batch (Eq. 9), beta (Eq. 10), c_agg, r_agg (Eqs. 11-12);
              TEC: timestamp, beta again, Eq. 13. One accept/reject for the whole batch, as in the paper.
  redact      not defined (LETA authenticates; it rewrites nothing) -> NotSupported.
  audit       not defined -> NotSupported.
No committee: the TEC verifies alone, so Exp. 2's committee_n axis does not change S99 (recorded as
"none (single TEC verifier)").
"""

import hashlib
import os
import time

import numpy as np

from veredact_bench.methods.baselines.s99_leta import construction as L
from veredact_bench.methods.scheme import (
    AuthCost,
    Authorization,
    Capabilities,
    Dataset,
    NotSupported,
    RedactionRequest,
    RedactionResult,
    Scheme,
)


def params(cfg: dict) -> L.Params:
    b = cfg["baselines"]["S99"]
    if (b["ring_n"], b["q"]) != (L.N, L.Q):
        raise ValueError("baselines.S99: the implementation is fixed to the FIPS 204 ring (n=256, q=8380417)")
    return L.Params(k=b["module_k"], tau=b["tau"], sigma_s=b["sigma_s"], gamma=b["gamma"])


class LETAScheme(Scheme):
    key = "S99"

    def __init__(self, cfg: dict):
        self.cfg, self.p, self.dt = cfg, params(cfg), cfg["baselines"]["S99"]["delta_t_s"]

    def capabilities(self) -> Capabilities:
        return Capabilities(
            pq_security=True,  # module lattice (the paper's claim; Sign has no rejection sampling, see construction)
            distributed_auth=False,  # one TEC verifies; the PL aggregates
            policy_control=False,  # possession of a registered key is the whole authorization
            batch_redaction=False,  # no redaction at all
            private_verification=True,  # pseudonyms + ZKP: the verifier never sees the real identity
            verifiable_auditing=False,
            state_freshness_check=False,  # T5 is message freshness, not the state a request was made against
            consensus_bound_auth=False,
        )

    def auth_cost(self) -> AuthCost:
        # per request: one h0 at the PL; per BATCH: one aggregate verification (Eq. 13), no signature generated
        return AuthCost()

    # ------------------------------------------------------------------ setup (untimed): TA + registration
    def setup(self, dataset: Dataset) -> None:
        self.S = L.setup(self.p, hashlib.sha3_256(b"S99-A" + str(dataset.seed).encode()).digest())
        rng = np.random.default_rng(dataset.seed)
        self.vehicles = [L.register(self.S, b"V%d" % i, rng) for i in range(dataset.requesters)]
        self.targets = {tx.tid for tx in dataset.transactions}

    def _sign(self, req: RedactionRequest):
        """Vehicle side (requester): Sign + ZKP over its request, and the Sec. IV-B4b identity message."""
        v = self.vehicles[req.requester]
        msg = hashlib.sha3_256(req.tid + req.new_payload).digest()
        sig = L.sign(self.S, v, msg)
        if req.fault == "sig":  # a forged signature: one response coefficient changed
            sig.r[0, 0] = (sig.r[0, 0] + 1) % L.Q
        t3 = int(time.time())
        m1 = L._b(L.h0(os.urandom(32)))
        m2 = L._b(L.h0(m1 + t3.to_bytes(8, "big")))
        return dict(v=v, msg=msg, sig=sig, eta=os.urandom(32), t2=t3, t3=t3, m1=m1, m2=m2)

    # ------------------------------------------------------------------ authorize: PL identity check
    def authorize(self, req: RedactionRequest) -> Authorization:
        if req.tid not in self.targets or req.fault == "absent":
            return Authorization(req, False, 0.0, reason="nonexistent target")
        h = self._sign(req)  # requester side, untimed
        t0 = time.perf_counter()
        ok = L._b(L.h0(h["m1"] + h["t3"].to_bytes(8, "big"))) == h["m2"]
        ms = (time.perf_counter() - t0) * 1000
        return Authorization(req, ok, ms, reason="" if ok else "identity check", handle=h)

    # ------------------------------------------------------------------ batch: aggregation + Eq. 13
    def authorize_batch(self, auths: list):
        hs = [a.handle for a in auths if a.ok]
        if not hs:
            return False, 0.0
        t0 = time.perf_counter()
        # PL: VPD-Tree, beta, aggregate (Eqs. 9-12)
        root = L.vpd_root([L.vpd_leaf(h["v"].pseudonym, h["sig"], h["eta"], h["t2"]) for h in hs])
        members = [(h["v"].pseudonym, h["t2"], h["sig"].mu) for h in hs]
        agg = L.aggregate(self.S, [h["sig"] for h in hs], members, root, int(time.time()))
        # TEC: timestamp, beta, Eq. 13
        ok = L.agg_verify(
            self.S,
            agg,
            members,
            [h["sig"].mu for h in hs],
            [h["v"].b for h in hs],
            [h["sig"].c for h in hs],
            int(time.time()),
            self.dt,
        )
        return ok, (time.perf_counter() - t0) * 1000

    def redact(self, batch: list) -> RedactionResult:
        raise NotSupported("S99: LETA authenticates vehicles; its paper defines no redaction")
