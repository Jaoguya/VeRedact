"""Cuckoo filter CF_s (Fan et al., CoNEXT 2014) screening SA-RLI / RAI lookup tokens per shard.

Partial-key cuckoo hashing: 16-bit fingerprints, 4 slots per bucket, a power-of-two bucket count so
the alternate bucket i2 = i1 xor h(fp) is an involution. Insert-only (index tokens are never removed:
SA-RLI entries are updated in place, RAI is historical). A full filter is rebuilt at twice the size
from the shard's tokens, so inserts never fail. No false negatives; false positives (~0.012% at 16 bits)
fall through to the authenticated lookup, as Phase 3 Step 1 prescribes.
"""

import hashlib
import random

SLOTS = 4
FP_BITS = 16
MAX_KICKS = 500
LOAD = 0.9


def _digest(token: bytes) -> int:
    return int.from_bytes(hashlib.blake2b(token, digest_size=8).digest(), "big")


class CuckooFilter:
    def __init__(self, capacity: int = 64):
        nb = 1
        while nb * SLOTS * LOAD < capacity:
            nb *= 2
        self.nb = nb
        self.buckets = [[] for _ in range(nb)]
        self.count = 0
        self._rng = random.Random(0)

    def _fp_i1(self, token: bytes):
        d = _digest(token)
        fp = (d >> 48) & ((1 << FP_BITS) - 1) or 1  # 0 is reserved for "empty"
        return fp, d % self.nb

    def _alt(self, i: int, fp: int) -> int:
        return (i ^ _digest(fp.to_bytes(2, "big"))) % self.nb

    def contains(self, token: bytes) -> bool:
        fp, i1 = self._fp_i1(token)
        return fp in self.buckets[i1] or fp in self.buckets[self._alt(i1, fp)]

    def insert(self, token: bytes) -> bool:
        """False only when the filter is full (the caller rebuilds it larger)."""
        fp, i1 = self._fp_i1(token)
        i2 = self._alt(i1, fp)
        for i in (i1, i2):
            if len(self.buckets[i]) < SLOTS:
                self.buckets[i].append(fp)
                self.count += 1
                return True
        i = self._rng.choice((i1, i2))
        for _ in range(MAX_KICKS):
            slot = self._rng.randrange(SLOTS)
            fp, self.buckets[i][slot] = self.buckets[i][slot], fp
            i = self._alt(i, fp)
            if len(self.buckets[i]) < SLOTS:
                self.buckets[i].append(fp)
                self.count += 1
                return True
        return False


def build(tokens) -> CuckooFilter:
    tokens = list(tokens)
    cap = max(64, len(tokens))
    while True:
        f = CuckooFilter(cap)
        if all(f.insert(t) for t in tokens):
            return f
        cap *= 2
