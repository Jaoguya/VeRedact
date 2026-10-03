"""PQZK: real transparent STARK (winterfell 0.13, native/pqzk_stark) for the policy relation R_P.

    Setup      credential registry: Rescue-Prime Merkle tree over Rescue(secret_r, requester_r, attribute_r,
               expiry_r) leaves; its root is what the policy commitment C_P binds to (Phase 1 Step 6,
               no trusted setup). Revoking a credential = removing its leaf (new root, new C_P version).
    Prove      witness (secret_r, attribute_r, expiry_r, leaf index, path); public (root, requester,
               policy threshold, request time ts_r, digest(x_i))
    Verify     STARK verification of R_P = ValidCred (membership + expiry > ts_r) AND RequesterBound AND
               PrivatePolicy (attribute_r >= threshold); attribute and expiry are never disclosed

The statement digest enters the Fiat-Shamir transcript, so a proof is bound to its request, state
version and epoch (Theorem 1). Build the extension once:  make build-zk
"""

import hashlib
import secrets
import time
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
    attribute_levels: int  # requester attributes and policy thresholds lie in 1..attribute_levels
    validity_s: int  # credential lifetime from registry setup


class PolicySTARK:
    name = "winterfell STARK (credential membership + expiry + attribute threshold + requester binding)"

    def __init__(self, params: ZKParams, requesters: int, seed: int, now_s: int | None = None):
        rng = secrets.SystemRandom() if seed is None else __import__("random").Random(seed)
        self.p = params
        size = 1 << params.depth
        now = int(time.time()) if now_s is None else now_s
        self._secret = [rng.getrandbits(_FIELD_BITS) for _ in range(requesters)]
        # every registered requester holds the top attribute level, so an honest request satisfies any
        # policy threshold; the predicate is still proven for each request
        self._attr = [params.attribute_levels] * requesters
        self._expiry = [now + params.validity_s] * requesters
        creds = [
            (self._secret[i], self.requester_element(i), self._attr[i], self._expiry[i]) for i in range(requesters)
        ]
        creds += [
            (
                rng.getrandbits(_FIELD_BITS),
                rng.getrandbits(_FIELD_BITS),
                rng.randint(1, params.attribute_levels),
                now + params.validity_s,
            )
            for _ in range(size - requesters)
        ]
        self.registry = _stark.Registry(creds)
        self.root = self.registry.root()
        self._paths = {}

    @staticmethod
    def requester_element(i: int) -> int:
        return int.from_bytes(hashlib.sha3_256(b"VRPQ-requester|%d" % i).digest()[:15], "big")

    def prove(
        self,
        requester: int,
        x: bytes,
        threshold: int,
        ts_s: int,
        secret_override: int | None = None,
        attribute_override: int | None = None,
    ) -> bytes:
        """A requester whose credential fails a predicate cannot build a proof: returns b"" (rejected)."""
        if requester not in self._paths:
            self._paths[requester] = self.registry.path(requester)
        secret = self._secret[requester] if secret_override is None else secret_override
        attr = self._attr[requester] if attribute_override is None else attribute_override
        p = self.p
        try:
            return _stark.prove(
                secret,
                self.requester_element(requester),
                attr,
                self._expiry[requester],
                requester,
                self._paths[requester],
                self.root,
                threshold,
                ts_s,
                statement_elements(x),
                p.queries,
                p.blowup,
                p.grinding,
            )
        except ValueError:
            return b""

    def verify(self, requester: int, x: bytes, proof: bytes, threshold: int, ts_s: int) -> bool:
        p = self.p
        return _stark.verify(
            proof,
            self.root,
            self.requester_element(requester),
            threshold,
            ts_s,
            statement_elements(x),
            p.queries,
            p.blowup,
            p.grinding,
        )
