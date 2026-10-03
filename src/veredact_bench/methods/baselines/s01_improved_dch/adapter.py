"""S1 [1] Li et al. Improved DCH on Jia et al.'s redactable chain, behind the shared Scheme contract
(docs/baselines/S1-improved-dch.md).

Chain (Jia, reviewed in [1] Sec. III-C): header = (prev_hash, last_hash, m_root, acc, r); the chameleon
hash covers everything except r; acc is an RSA accumulator over the headers of redacted blocks.
[1] replaces Jia's DCH with Improved DCH and extends the header field to curr_hash&rand (Sec. V-B).

  authorize  Sec. III-C3 steps 1-3: t full nodes each (a) check via acc that block B was not redacted
             before — a non-membership witness built once by the initiating node, verified by every
             approver (Jia's chain allows ONE redaction per block — a real limit, reported as rejections),
             (b) verify the signatures of tx and tx' (ECDSA secp256k1).
  redact     step 3-5: threshold Collision over the new header content (t parties, Improved DCH),
             txreq anchored on the ledger, acc <- acc^{prime(header')}.
  audit      Sec. III-C4 consistency check per queried block: integrity (Improved DCH Verify) + RSA
             accumulator membership witness for the redaction.
"""
import hashlib
import time

import gmpy2

from coincurve import PrivateKey
from cryptography.hazmat.primitives.asymmetric import rsa
from veredact_bench.methods.baselines.s01_improved_dch.construction import ImprovedDCH, dkg

from veredact_bench.evaluation.anchor import gather, make_anchor
from veredact_bench.methods.scheme import (AuditQuery, AuditResult, AuthCost, Authorization, Capabilities, Dataset,
                                   RedactionOutcome, RedactionResult, RedactionRequest, Scheme)


def _hprime(data: bytes) -> int:
    """hash-to-prime for the RSA accumulator (Jia's ACC.Insert)."""
    return int(gmpy2.next_prime(int.from_bytes(hashlib.sha256(b"ACC|" + data).digest(), "big") | 1))


def _mroot(payloads):
    level = [hashlib.sha256(p).digest() for p in payloads]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0]


class ImprovedDCHScheme(Scheme):
    key = "S1"

    def __init__(self, cfg: dict, nodes_n: int | None = None, threshold_t: int | None = None):
        b = cfg["baselines"]["S1"]
        self.cfg, self.n, self.t, self.acc_bits = cfg, nodes_n or b["nodes_n"], threshold_t or b["threshold_t"], \
            b["accumulator_rsa_bits"]

    def capabilities(self) -> Capabilities:
        return Capabilities(pq_security=False, distributed_auth=True, policy_control=False, batch_redaction=False,
                            private_verification=False, verifiable_auditing=True, state_freshness_check=False,
                            consensus_bound_auth=False)

    def auth_cost(self) -> AuthCost:
        return AuthCost(signature_verifications=2 * self.t)

    # ------------------------------------------------------------------ setup (untimed)
    def setup(self, dataset: Dataset) -> None:
        self.key_ = dkg(self.t, self.n)
        self.dch = ImprovedDCH(self.key_)
        self.parties = list(self.key_.shares)[: self.t]
        self.owners = [PrivateKey() for _ in range(dataset.requesters)]
        nums = rsa.generate_private_key(public_exponent=65537, key_size=self.acc_bits).private_numbers()
        self.N = nums.public_numbers.n
        self.g = pow(3, 2, self.N)
        self.acc, self.members, self.u = self.g, [], 1  # acc = g^u, u = product of redacted-header primes
        N_leaves = self.cfg["dataset"]["leaves_per_batch"]
        self.blocks, self.block_of, self.sig = [], {}, {}
        prev = b"genesis"
        for off in range(0, len(dataset.transactions), N_leaves):
            chunk = dataset.transactions[off:off + N_leaves]
            payloads = [t.payload for t in chunk]
            msg = prev + _mroot(payloads)
            hv = self.dch.hash(msg)
            self.blocks.append({"prev": prev, "payloads": payloads, "msg": msg, "h": hv.h, "r": hv.r, "redacted": False})
            for pos, t in enumerate(chunk):
                self.block_of[t.tid] = (len(self.blocks) - 1, pos)
                self.sig[t.tid] = self.owners[t.owner].sign(t.payload)
            prev = hashlib.sha256(hv.h.to_compressed_bytes()).digest()
        self.anchor = make_anchor(self.cfg)
        self.redacted = []  # (seq, block)

    # ------------------------------------------------------------------ authorize: steps 1-3
    def authorize(self, req: RedactionRequest) -> Authorization:
        if req.tid not in self.block_of or req.fault == "absent":
            return Authorization(req, False, 0.0, reason="nonexistent target")
        b, pos = self.block_of[req.tid]
        owner = self.owners[int(req.tid[2:]) % len(self.owners)]
        new_sig = owner.sign(req.new_payload)  # the new transaction tx' is signed by its creator (untimed)
        blk = self.blocks[b]
        t0 = time.perf_counter()
        if blk["redacted"]:  # membership in acc (Jia: one redaction per block) -> rejected
            return Authorization(req, False, (time.perf_counter() - t0) * 1000, reason="block already redacted")
        # "not yet redacted" is shown against acc by a non-membership witness (a, B): a*u + b*x = 1, B = g^b,
        # checked as acc^a * B^x = g; the initiating node P builds it once, every approving node verifies it
        x = _hprime(blk["msg"])
        g_, a_, b_ = gmpy2.gcdext(self.u, x)
        B = gmpy2.powmod(self.g, b_, self.N)
        for _ in range(self.t):  # each approving full node
            if gmpy2.powmod(self.acc, a_, self.N) * gmpy2.powmod(B, x, self.N) % self.N != self.g:
                return Authorization(req, False, (time.perf_counter() - t0) * 1000, reason="block already redacted")
            pk = owner.public_key
            if not (pk.verify(self.sig[req.tid], blk["payloads"][pos]) and pk.verify(new_sig, req.new_payload)):
                return Authorization(req, False, (time.perf_counter() - t0) * 1000, reason="tx signature")
        return Authorization(req, True, (time.perf_counter() - t0) * 1000, handle=(b, pos))

    # ------------------------------------------------------------------ redact: steps 3-5
    def redact(self, batch: list) -> RedactionResult:
        crypto_ms, outcomes, futs = 0.0, [], []
        for a in batch:
            if not a.ok:
                outcomes.append(RedactionOutcome(a.request.seq, False, reason=a.reason))
                continue
            b, pos = a.handle
            blk = self.blocks[b]
            if blk["redacted"]:  # a second request to the same block in this round
                outcomes.append(RedactionOutcome(a.request.seq, False, stale=True, reason="block already redacted"))
                continue
            t0 = time.perf_counter()
            payloads = list(blk["payloads"])
            payloads[pos] = a.request.new_payload
            msg_new = blk["prev"] + _mroot(payloads)
            r_new = self.dch.collision(blk["msg"], msg_new, blk["r"], blk["h"], self.parties)
            ok = self.dch.verify(msg_new, r_new, blk["h"])
            x = _hprime(msg_new)
            self.acc = int(gmpy2.powmod(self.acc, x, self.N))
            self.u *= x
            crypto_ms += (time.perf_counter() - t0) * 1000
            if ok:
                blk.update(payloads=payloads, msg=msg_new, r=r_new, redacted=True)
                self.members.append(x)
                # pipelined like VeRedact's anchoring: finality is tracked by the Future, not awaited here
                futs.append(self.anchor.submit("baseline_redaction", tid=a.request.tid.ljust(32, b"\0")[:32],
                                               commit=hashlib.sha256(msg_new).digest(), version=1,
                                               evidence=r_new.to_compressed_bytes()))
                self.redacted.append((a.request.seq, b))
            outcomes.append(RedactionOutcome(a.request.seq, ok))
        return RedactionResult(outcomes, crypto_ms, 0.0, len(futs), finality=gather(futs) if futs else None,
                               finality_op="baseline_redaction")

    # ------------------------------------------------------------------ audit: consistency check
    def audit(self, query: AuditQuery) -> AuditResult:
        recs = self.redacted[: query.records]
        t0 = time.perf_counter()
        evidence = []
        for i, (_, b) in enumerate(recs):  # node: block + membership witness u^{prod of the other primes}
            blk = self.blocks[b]
            x = _hprime(blk["msg"])
            others = 1
            for m in self.members:
                if m != x:
                    others *= m
            evidence.append((b, blk["msg"] if i not in query.tamper else blk["msg"] + b"!", blk["r"],
                             int(gmpy2.powmod(self.g, others, self.N))))
        t1 = time.perf_counter()
        accepted = {}
        for i, (b, msg, r, wit) in enumerate(evidence):  # client: integrity, then membership
            ok = self.dch.verify(msg, r, self.blocks[b]["h"]) and int(gmpy2.powmod(wit, _hprime(msg), self.N)) == self.acc
            accepted[i] = ok
        t2 = time.perf_counter()
        nbytes = sum(len(m) + 48 + self.N.bit_length() // 8 for _, m, _, _ in evidence)
        return AuditResult("block consistency: redacted-or-not (Jia Sec. III-C4)", (t1 - t0) * 1000,
                           (t2 - t1) * 1000, nbytes, accepted)

    def teardown(self) -> None:
        self.anchor.close()
