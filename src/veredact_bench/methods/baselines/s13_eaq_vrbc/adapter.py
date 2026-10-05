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

Measurement (harness, not the paper): Alg. 1's witness B = u^b mod N has |b| ~ |theta|, so one witness costs
seconds at the experiment's 10^4-redaction history. A challenged block's witness depends only on the block
and theta, which audits do not change, so index_records() builds every block's witness ONCE after the
untimed history (process pool, one core per witness, each timed in its worker). An audit then uses those
exact witnesses: response bytes and verification are measured directly; generation time = the summed
single-core witness times of its blocks + the directly measured challenge-dependent aggregation.
"""

import os
import time
from concurrent.futures import ProcessPoolExecutor

from veredact_bench.evaluation.anchor import gather, make_anchor
from veredact_bench.methods.baselines.s13_eaq_vrbc.construction import Ledger, nonmem_create_raw
from veredact_bench.methods.baselines.s13_eaq_vrbc.construction import setup as s13_setup
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
from veredact_bench.utils.log import get_logger


class EAQVRBCScheme(Scheme):
    key = "S13"

    def __init__(self, cfg: dict):
        self.cfg, self.b = cfg, cfg["baselines"]["S13"]

    def capabilities(self) -> Capabilities:
        return Capabilities(
            pq_security=False,
            distributed_auth=False,
            policy_control=False,
            batch_redaction=False,
            private_verification=False,
            verifiable_auditing=True,
            state_freshness_check=True,
            consensus_bound_auth=False,
        )

    def auth_cost(self) -> AuthCost:
        return AuthCost()  # key-possession check only: no signature/proof verification, no network

    def setup(self, dataset: Dataset) -> None:
        self.p = s13_setup(self.b["rsa_bits"], self.b["miners"], self.b["l_bits"])
        self.L = Ledger(self.p)
        N = self.cfg["dataset"]["leaves_per_batch"]
        self.block_of, self.txs = {}, {}
        for off in range(0, len(dataset.transactions), N):
            chunk = dataset.transactions[off : off + N]
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
            futs.append(
                self.anchor.submit(
                    "baseline_redaction",
                    tid=a.request.tid.ljust(32, b"\0")[:32],
                    commit=self.L.blocks[s].m[:32],
                    version=len(self.L.acc.revoked),
                    evidence=tag,
                )
            )
            self.redacted.append((a.request.seq, s))
            outcomes.append(RedactionOutcome(a.request.seq, True))
        return RedactionResult(
            outcomes,
            crypto_ms,
            0.0,
            len(futs),
            finality=gather(futs) if futs else None,
            finality_op="baseline_redaction",
        )

    def index_records(self) -> None:
        """After the (untimed) history: Alg. 1 witness of every redacted block, built once and timed per
        witness on one core. Built in parallel on one worker per PHYSICAL core (hyperthread siblings slow each
        other: a timing bias against S13); a few are re-timed serially, and if parallel times are inflated by
        more than 10 % every witness is re-timed serially, so the reported times are single-core times."""
        u, N, theta = self.p.u, self.p.N, self.L.acc.theta()
        blocks = sorted({s for _, s in self.redacted})
        xs = [self.p.H1(i, self.L.tags[i][2]) for i in blocks]
        workers = max(1, min(self.cfg["environment"]["vcpus"] // 2, os.cpu_count() or 1))
        with ProcessPoolExecutor(workers, initializer=_wit_init, initargs=(u, N, theta)) as ex:
            built = list(ex.map(_wit_job, xs))
        _wit_init(u, N, theta)
        k = min(4, len(xs))
        solo = [_wit_job(x)[1] for x in xs[:k]]
        par = [ms for _, ms in built[:k]]
        ratio = (sorted(solo)[k // 2] / sorted(par)[k // 2]) if k else 1.0
        if ratio < 0.9:  # parallel timing inflated: time every witness on its own instead
            built = [(w, _wit_job(x)[1]) for (w, _), x in zip(built, xs)]
        self.witness_calibration = ratio
        self._theta_n = len(self.L.acc.revoked)
        self._wit = {i: (x, w, ms) for i, x, (w, ms) in zip(blocks, xs, built)}
        get_logger().info(
            f"  S13 witnesses: {len(xs)} blocks on {workers} workers, serial/parallel = {ratio:.2f}"
            f"{' -> re-timed serially' if ratio < 0.9 else ''}, median "
            f"{sorted(ms for _, _, ms in self._wit.values())[len(xs) // 2]:.0f} ms each"
        )

    def _cached_witnesses(self, chal):
        """The prebuilt witnesses, if they are still Alg. 1's output for the current accumulator and tags."""
        w = getattr(self, "_wit", None)
        if not w or self._theta_n != len(self.L.acc.revoked):
            return None
        out = {}
        for i, _ in chal:
            x, wit, _ms = w.get(i, (None, None, 0))
            if x != self.p.H1(i, self.L.tags[i][2]):
                return None
            out[i] = wit
        return out

    def audit(self, query: AuditQuery) -> AuditResult:
        blocks = sorted({s for _, s in self.redacted[: query.records]})
        chal = [(i, int.from_bytes(os.urandom(8), "big") + 1) for i in blocks]
        saved = {}
        for s in {self.redacted[idx][1] for idx in query.tamper}:  # Exp. 4: corrupt each tampered block's tag ONCE
            saved[s] = self.L.tags[s]  # (two records in one block must not flip the same bit back)
            t, c, hh = self.L.tags[s]
            self.L.tags[s] = (type(t)(t.S ^ 1, t.v), c, hh)
        ck = (query.records, tuple(sorted(query.tamper.items())))
        cached = getattr(self, "_responses", {}).get(ck) if query.reuse_response else None
        if cached:  # Exp. 4: same challenge + proof again; only the auditor's verification is re-timed
            chal, proof, gen_ms = cached
        else:
            wits = self._cached_witnesses(chal)
            t0 = time.perf_counter()
            proof = self.L.audit_prove(chal, wits)  # identical response either way
            gen_ms = (time.perf_counter() - t0) * 1000
            if wits:  # + each witness's own measured single-core build time (index_records)
                gen_ms += sum(self._wit[i][2] for i, _ in chal)
            if query.reuse_response:
                self.__dict__.setdefault("_responses", {})[ck] = (chal, proof, gen_ms)
        t1 = time.perf_counter()
        ok = self.L.audit_verify(chal, proof)
        t2 = time.perf_counter()
        self.L.tags.update(saved)
        (V, S), mu, w = proof
        nbytes = (
            2 * (self.p.N.bit_length() // 8)
            + (mu.bit_length() + 7) // 8
            + sum((x.bit_length() + 7) // 8 for x in (w.a, w.B, w.C, w.D, w.pi_C, w.pi_D))
            + 16 * len(w.xs)
        )
        return AuditResult(
            "ledger integrity + version freshness (aggregate, per challenged set)",
            gen_ms,
            (t2 - t1) * 1000,
            nbytes,
            {i: ok for i in range(min(query.records, len(self.redacted)))},
        )

    def teardown(self) -> None:
        self.anchor.close()


_W: tuple = ()


def _wit_init(u: int, N: int, theta: int) -> None:
    global _W
    _W = (u, N, theta)  # theta is large: sent once per worker, not once per witness


def _wit_job(x: int):
    t0 = time.perf_counter()
    w = nonmem_create_raw(*_W, x)
    return w, (time.perf_counter() - t0) * 1000
