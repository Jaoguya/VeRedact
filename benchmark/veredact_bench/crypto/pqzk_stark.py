"""PQZK: real transparent STARK (winterfell 0.13, benchmark/pqzk_stark) for the policy relation R_P.

    Setup      credential registry: Rescue-Prime Merkle tree over Rescue(secret_r, requester_r) leaves;
               its root is what the policy commitment C_P binds to (Phase 1 Step 6, no trusted setup)
    Prove      witness (secret_r, leaf index, path); public (root, requester, digest(x_i))
    Verify     STARK verification against (root, requester, digest(x_i))

The statement digest enters the Fiat-Shamir transcript, so a proof is bound to its request, state
version and epoch (Theorem 1). Build the extension once:  make build-zk
"""
import hashlib
import secrets
from dataclasses import dataclass

try:
    import vrpq_stark as _stark
except ImportError as e:  # pragma: no cover
    raise ImportError("vrpq_stark extension missing: run `make build-zk`") from e

_FIELD_BITS = 120  # fits the f128 field (modulus ~ 2^128 - 45*2^40 + 1)


def statement_elements(x: bytes) -> tuple[int, int]:
    d = hashlib.sha3_256(b"VRPQ-PQZK-x|" + x).digest()
    mask = (1 << _FIELD_BITS) - 1
    return int.from_bytes(d[:16], "big") & mask, int.from_bytes(d[16:], "big") & mask


@dataclass(frozen=True)
class ZKParams:
    queries: int
    blowup: int
    grinding: int
    depth: int


class PolicySTARK:
    name = "winterfell STARK (Rescue-Prime Merkle membership + requester binding)"

    def __init__(self, params: ZKParams, requesters: int, seed: int):
        rng = secrets.SystemRandom() if seed is None else __import__("random").Random(seed)
        self.p = params
        size = 1 << params.depth
        self._secret = [rng.getrandbits(_FIELD_BITS) for _ in range(requesters)]
        creds = [(self._secret[i], self.requester_element(i)) for i in range(requesters)]
        creds += [(rng.getrandbits(_FIELD_BITS), rng.getrandbits(_FIELD_BITS)) for _ in range(size - requesters)]
        self.registry = _stark.Registry(creds)
        self.root = self.registry.root()
        self._paths = {}

    @staticmethod
    def requester_element(i: int) -> int:
        return int.from_bytes(hashlib.sha3_256(b"VRPQ-requester|%d" % i).digest()[:15], "big")

    def prove(self, requester: int, x: bytes, secret_override: int | None = None) -> bytes:
        if requester not in self._paths:
            self._paths[requester] = self.registry.path(requester)
        secret = self._secret[requester] if secret_override is None else secret_override
        p = self.p
        return _stark.prove(secret, self.requester_element(requester), requester, self._paths[requester],
                            self.root, statement_elements(x), p.queries, p.blowup, p.grinding)

    def verify(self, requester: int, x: bytes, proof: bytes) -> bool:
        p = self.p
        return _stark.verify(proof, self.root, self.requester_element(requester), statement_elements(x),
                             p.queries, p.blowup, p.grinding)
