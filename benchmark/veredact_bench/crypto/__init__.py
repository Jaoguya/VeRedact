"""Crypto facade: one object bundling the primitives, with per-operation counters and timers.

Counter names follow the cost-analysis notation (Table III/IV of the paper):
  T_S, T_V (PQ sign/verify) · T_Sc, T_Vc (classical) · T_ZP, T_ZV (PQZK) · T_CH (PQCH hash)
  T_PA, T_CB (PQCH partial adapt / combine) · T_AD (centralized adapt) · T_H · T_PRF · T_Pol
"""
import time
from collections import Counter, defaultdict
from contextlib import contextmanager

from . import hashing
from .pqch import LinearThresholdCH
from .pqsig import Ed25519, load_pqsig
from .pqzk import SimulatedSTARK, burn


class Crypto:
    def __init__(self, sig_backend=None, zk=None, ch_dim=256, classical_sigs=False, policy_ms=4.0):
        self.sig = Ed25519() if classical_sigs else load_pqsig(sig_backend)
        self.pq = not classical_sigs
        self.zk = zk or SimulatedSTARK()
        self.ch = LinearThresholdCH(dim=ch_dim)
        self.policy_ms = policy_ms  # T_Pol stand-in (policy-based CH authorization, e.g. ABE decryption)
        self.counts: Counter = Counter()
        self.time_s: defaultdict = defaultdict(float)

    # ---- accounting ------------------------------------------------------
    @contextmanager
    def _op(self, name):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.counts[name] += 1
            self.time_s[name] += time.perf_counter() - t

    def reset(self):
        self.counts.clear()
        self.time_s.clear()

    def snapshot(self):
        return dict(self.counts), {k: v * 1000 for k, v in self.time_s.items()}

    # ---- hashing / PRF ---------------------------------------------------
    def H(self, *p):
        self.counts["T_H"] += 1
        return hashing.H(*p)

    def H1(self, *p):
        self.counts["T_H"] += 1
        return hashing.H1(*p)

    def H2(self, *p):
        self.counts["T_H"] += 1
        return hashing.H2(*p)

    def HA(self, *p):
        self.counts["T_H"] += 1
        return hashing.HA(*p)

    def PRF(self, key, *p):
        self.counts["T_PRF"] += 1
        return hashing.PRF(key, *p)

    # ---- signatures ------------------------------------------------------
    def keygen(self):
        return self.sig.keygen()

    def sign(self, sk, msg):
        with self._op("T_S" if self.pq else "T_Sc"):
            return self.sig.sign(sk, msg)

    def verify(self, pk, msg, sig):
        with self._op("T_V" if self.pq else "T_Vc"):
            return self.sig.verify(pk, msg, sig)

    # ---- PQZK ------------------------------------------------------------
    def zk_prove(self, params, x, w, relation):
        with self._op("T_ZP"):
            return self.zk.prove(params, x, w, relation)

    def zk_verify(self, params, x, proof):
        with self._op("T_ZV"):
            return self.zk.verify(params, x, proof)

    # ---- PQCH ------------------------------------------------------------
    def ch_hash(self, pk, msg, r):
        with self._op("T_CH"):
            return self.ch.hash(pk, msg, r)

    def ch_part_adapt(self, td, msg, r, msg_new, ctx=b""):
        with self._op("T_PA"):
            return self.ch.part_adapt(td, msg, r, msg_new, ctx)

    def ch_combine(self, shares, r):
        with self._op("T_CB"):
            return self.ch.combine(shares, r)

    def ch_adapt(self, T, msg, r, msg_new):
        with self._op("T_AD"):
            return self.ch.adapt(T, msg, r, msg_new)

    # ---- policy-based authorization stand-in (baselines' T_Pol) -----------
    def policy_auth(self):
        with self._op("T_Pol"):
            burn(self.policy_ms)


__all__ = ["Crypto", "hashing"]
