"""Crypto facade for VeRedact-PQ: real primitives only, with per-operation counters and timers.

Counter names follow the manuscript's cost notation (Table III):
  T_S, T_V (ML-DSA-65 sign/verify) · T_ZP, T_ZV (STARK prove/verify) · T_CH (PQCH hash)
  T_PA, T_CB (PQCH partial adaptation / combination) · T_H (SHA3-256) · T_PRF (HMAC-SHA3-256)
The counts let every measured number be reconciled against the analytical Table IV.
"""
import time
from collections import Counter, defaultdict
from contextlib import contextmanager

from . import hashing
from .pqch_sis import SISChameleonHash, default_params
from .pqsig import load_pqsig
from ..config import REPO_ROOT
from .pqzk_stark import PolicySTARK, ZKParams


class Crypto:
    def __init__(self, cfg: dict, requesters: int):
        sec = cfg["security"]
        self.sig = load_pqsig()
        ch = sec["pqch"]
        self.ch = SISChameleonHash(default_params(n=ch["n"], k=ch["k"], sigma_R=ch["sigma_R"],
                                                  sigma_g=ch["sigma_g"]), seed=cfg["meta"]["seed"],
                                   cache_dir=REPO_ROOT / "benchmark" / ".cache" / "pqch_dkg")
        z = sec["pqzk"]
        self.zk = PolicySTARK(ZKParams(z["queries"], z["blowup"], z["grinding_bits"], z["registry_depth"]),
                              requesters, cfg["meta"]["seed"])
        self.counts: Counter = Counter()
        self.time_s: defaultdict = defaultdict(float)

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

    # ---- hashing / PRF ---------------------------------------------------------------------------
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

    # ---- ML-DSA-65 -------------------------------------------------------------------------------
    def keygen(self):
        return self.sig.keygen()

    def sign(self, sk, msg):
        with self._op("T_S"):
            return self.sig.sign(sk, msg)

    def verify(self, pk, msg, sig):
        with self._op("T_V"):
            return self.sig.verify(pk, msg, sig)

    # ---- STARK -------------------------------------------------------------------------------------
    def zk_prove(self, requester, x, secret_override=None):
        with self._op("T_ZP"):
            return self.zk.prove(requester, x, secret_override)

    def zk_verify(self, requester, x, proof):
        with self._op("T_ZV"):
            return self.zk.verify(requester, x, proof)

    # ---- PQCH (SIS / MP12, distributed) -------------------------------------------------------------
    def ch_hash(self, pk, msg, r):
        with self._op("T_CH"):
            return self.ch.hash(pk, msg, r)

    def ch_verify(self, pk, ch, msg, r):
        with self._op("T_CH"):
            return self.ch.verify(pk, ch, msg, r)

    def ch_begin_adapt(self, pk, msg, r, msg_new):
        with self._op("T_CB_prep"):  # combiner-side perturbation + SampleG (reported with T_CB)
            return self.ch.begin_adapt(pk, msg, r, msg_new)

    def ch_part_adapt(self, share, z):
        with self._op("T_PA"):
            return self.ch.part_adapt(share, z)

    def ch_combine(self, pert, z, deltas):
        with self._op("T_CB"):
            return self.ch.combine(pert, z, deltas)


__all__ = ["Crypto", "hashing"]
