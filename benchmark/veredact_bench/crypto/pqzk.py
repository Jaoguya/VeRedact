"""PQZK: transparent hash-based STARK for the policy relation R_P (Phase 1 Step 6, Phase 3 Step 4).

The paper leaves the STARK library as [TBD]. Until one is wired in, SimulatedSTARK reproduces the
*cost profile* (prove/verify CPU time, proof size) and the *binding* behaviour (a proof only verifies
for the exact statement it was produced for, and only if R_P(x, w) held at proving time).

It is NOT zero-knowledge or sound against a real adversary. Replace `SimulatedSTARK` with an
adapter over the chosen library (e.g. winterfell / stone-prover via subprocess) keeping this interface.
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Callable

from .hashing import H


def burn(ms: float):
    """Busy CPU work for `ms` milliseconds (hash chain), so simulated costs load the CPU like real ones."""
    if ms <= 0:
        return
    end = time.perf_counter() + ms / 1000
    d = b"\0" * 32
    while time.perf_counter() < end:
        for _ in range(64):
            d = hashlib.sha3_256(d).digest()


@dataclass
class ZKParams:
    pp: bytes
    pk: bytes
    vk: bytes


class SimulatedSTARK:
    name = "SIMULATED STARK (insecure)"

    def __init__(self, prove_ms=300.0, verify_ms=5.0, proof_bytes=80_000):
        self.prove_ms, self.verify_ms, self.proof_bytes = prove_ms, verify_ms, proof_bytes
        self._issued: set[bytes] = set()

    def setup(self, relation_id: str) -> ZKParams:
        pp = H("PQZK.Setup", relation_id)  # transparent: no trapdoor
        return ZKParams(pp, H("pk", pp), H("vk", pp))

    def prove(self, params: ZKParams, x: bytes, w, relation: Callable) -> bytes:
        burn(self.prove_ms)
        ok = bool(relation(x, w))
        tag = H("PQZK.proof", params.pk, x, b"\1" if ok else b"\0")
        if ok:
            self._issued.add(tag)
        return tag + bytes(self.proof_bytes - len(tag))

    def verify(self, params: ZKParams, x: bytes, proof: bytes) -> bool:
        burn(self.verify_ms)
        tag = proof[:32]
        return tag == H("PQZK.proof", params.pk, x, b"\1") and tag in self._issued
