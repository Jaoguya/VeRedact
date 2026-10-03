"""S34 [34] REBS behind the shared Scheme contract (docs/baselines/S34-rebs.md).

Paper workflow (Sec. V), per request:
  authorize  the transaction redactor (TR) decrypts Info_Trap with the attribute keys the AVNs issued it
             (AttrKeyGen: one Sig_AMC check per attribute). Decryption succeeds only if its attribute
             VALUES satisfy the hidden (t, l) LSSS policy — the paper's whole authorization. There is no
             signature on the request, no requester proof, no freshness check: the paper defines none.
  redact     ChCld: r~ = (h H(Tx')^{-t})^d with d = e^{-1} mod phi(n n~); nodes run ChVer; one ledger
             write per redaction (the paper has no batching).
  audit      not defined ("authorizable verification" = only AVN-authorised nodes verify attributes;
             there is no audit query) -> NotSupported.

Deviations (bias direction in docs/baselines/S34-rebs.md):
  * AttrKeyGen runs at setup, once per (TR, policy) the trace needs; the paper also issues keys once per
    identity, so authorize() times only decryption (favours S34 by the one-off Sig_AMC checks).
  * CHash (ephemeral RSA key per transaction) is materialised only for transactions the trace targets;
    the rest of the corpus is never read by any S34 operation. Ephemeral keygen runs in a process pool.
  * Composite-order group -> prime-order BLS12-381 (s34_scheme.py header).
"""
import hashlib
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s34_scheme as R  # noqa: E402

from veredact_bench.anchor import gather, make_anchor  # noqa: E402
from veredact_bench.scheme import (AuthCost, Authorization, Capabilities, Dataset, RedactionOutcome,  # noqa: E402
                                   RedactionResult, RedactionRequest, Scheme)


class REBSScheme(Scheme):
    key = "S34"

    def __init__(self, cfg: dict, policy_attributes: int | None = None, policy_threshold: int | None = None):
        b = cfg["baselines"]["S34"]
        self.cfg, self.bits = cfg, b["rsa_bits"]
        self.l = policy_attributes or b["policy_attributes"]
        self.t = policy_threshold or b["policy_threshold"]

    def capabilities(self) -> Capabilities:
        return Capabilities(pq_security=False, distributed_auth=True, policy_control=True, batch_redaction=False,
                            private_verification=True, verifiable_auditing=False, state_freshness_check=False,
                            consensus_bound_auth=False)

    def auth_cost(self) -> AuthCost:
        # decryption: 2t pairings + t GT exponentiations; no signature, proof or network round trip
        return AuthCost()

    # ------------------------------------------------------------------ setup (untimed)
    def setup(self, dataset: Dataset) -> None:
        self.amc = R.gpgen(self.bits)
        # one AVN per policy attribute: attribute i's key uses AVN_i's (eps_i, eta_i) (paper Sec. V, KeyAVN)
        self.attr_auth = [R.key_avn() for _ in range(self.l)]
        A = R.lsss_threshold(self.l, self.t)
        self.policies = [R.Policy(A, [R.rnd() for _ in range(self.l)], self.t) for _ in range(dataset.policies)]
        self.trs = {}  # requester -> (k_TR, Sig_AMC)
        self.keys = {}  # (requester, policy used for the attribute values) -> {row: k_attr}
        self.by_tid = {tx.tid: tx for tx in dataset.transactions}
        targets = list(dict.fromkeys(r.tid for r in dataset.trace if r.tid in self.by_tid))
        workers = min(self.cfg["environment"]["vcpus"], os.cpu_count() or 1)
        with ProcessPoolExecutor(workers) as ex:
            eph = list(ex.map(R.rsa_key, [self.bits] * len(targets)))
        self.ch = {}
        for tid, e in zip(targets, eph):
            tx = self.by_tid[tid]
            self.ch[tid] = R.chash(self.amc, self.attr_auth, self.policies[tx.policy], tx.payload, tx.ts, self.bits, e)[0]
        for r in dataset.trace:
            if r.tid in self.by_tid:
                self._issue(r.requester, self._values_policy(r))
        self.anchor = make_anchor(self.cfg)

    def _values_policy(self, req: RedactionRequest) -> int:
        """Whose attribute values the TR holds: the target's policy, or (policy fault) another one's."""
        p = self.by_tid[req.tid].policy
        return (p + 1) % len(self.policies) if req.fault == "policy" else p

    def _issue(self, requester: int, p: int) -> None:
        if requester not in self.trs:
            self.trs[requester] = R.key_tr(self.amc, self._id(requester))
        if (requester, p) not in self.keys:
            _, sig = self.trs[requester]
            self.keys[(requester, p)] = {
                l: R.attr_keygen(self.amc, self.attr_auth[l], self._id(requester), sig, self.policies[p].values[l])
                for l in range(self.l)}

    @staticmethod
    def _id(requester: int) -> bytes:
        return b"TR%d" % requester

    # ------------------------------------------------------------------ authorize: policy decryption
    def authorize(self, req: RedactionRequest) -> Authorization:
        if req.tid not in self.ch or req.fault == "absent":
            return Authorization(req, False, 0.0, reason="nonexistent target")
        tx = self.by_tid[req.tid]
        vp = self._values_policy(req)
        self._issue(req.requester, vp)  # one-off per (TR, attribute values); a no-op for trace requests
        keys = self.keys[(req.requester, vp)]
        t0 = time.perf_counter()
        trap = R.recover_trap(self.policies[tx.policy], self.ch[req.tid].info, self._id(req.requester), keys)
        ms = (time.perf_counter() - t0) * 1000
        if trap is None:
            return Authorization(req, False, ms, reason="attribute policy not satisfied")
        return Authorization(req, True, ms, handle=trap)

    # ------------------------------------------------------------------ redact: ChCld + ChVer
    def redact(self, batch: list) -> RedactionResult:
        crypto_ms, outcomes, adapt, futs = 0.0, [], 0, []
        for a in batch:
            if not a.ok:
                outcomes.append(RedactionOutcome(a.request.seq, False, reason=a.reason))
                continue
            tid = a.request.tid
            k_tr, _ = self.trs[a.request.requester]
            t0 = time.perf_counter()
            v2 = R.chcld(self.amc, k_tr, a.handle, self.ch[tid], a.request.new_payload)
            ok = R.chver(self.amc, a.request.new_payload, v2)  # ChCld step 4: the TR checks before broadcasting
            ok = ok and R.chver(self.amc, a.request.new_payload, v2)  # the AVNs validate it for consensus
            crypto_ms += (time.perf_counter() - t0) * 1000
            adapt += 1
            if ok:
                self.ch[tid] = v2
                r_bytes = v2.r.to_bytes((v2.r.bit_length() + 7) // 8, "big")
                # pipelined like VeRedact's anchoring: finality is tracked by the Future, not awaited here
                futs.append(self.anchor.submit("baseline_redaction", tid=tid.ljust(32, b"\0")[:32],
                                               commit=hashlib.sha256(r_bytes).digest(), version=1,
                                               evidence=r_bytes))
            outcomes.append(RedactionOutcome(a.request.seq, ok, reason="" if ok else "ChVer"))
        return RedactionResult(outcomes, crypto_ms, 0.0, adapt, finality=gather(futs) if futs else None,
                               finality_op="baseline_redaction")

    def teardown(self) -> None:
        self.anchor.close()
