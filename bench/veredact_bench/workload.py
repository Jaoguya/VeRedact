"""Synthetic enterprise workload (Sec. Experimental Setup).

- payloads 256 B .. 4 KB
- redaction targets: Zipf with skew s over transaction batches (s = 0 -> uniform), uniform inside a batch
- arrivals: Poisson(rate), optionally bursty on/off phases for ABRRR adaptation
- fault injection: fraction of malformed / replayed / nonexistent / bad-signature / bad-proof requests
"""
import os
import random

import numpy as np

from .config import D


def payloads(count: int, lo=D.payload_min, hi=D.payload_max, seed=0) -> list[bytes]:
    rng = random.Random(seed)
    return [os.urandom(rng.randint(lo, hi)) for _ in range(count)]


class ZipfTargets:
    """Pick target TIDs with batch-level Zipf skew s."""

    def __init__(self, ledger, s: float, seed=0):
        self.rng = np.random.default_rng(seed)
        self.batches = sorted(ledger.batches)
        ranks = np.arange(1, len(self.batches) + 1, dtype=float)
        w = ranks ** (-s) if s > 0 else np.ones_like(ranks)
        self.p = w / w.sum()
        self.rng.shuffle(self.batches)  # hot batches are not simply the oldest ones
        self.L = ledger

    def pick(self) -> bytes:
        b = self.batches[self.rng.choice(len(self.batches), p=self.p)]
        tids = self.L.batches[b].tids
        return tids[self.rng.integers(len(tids))]

    def pick_many(self, k):
        return [self.pick() for _ in range(k)]


def poisson_arrivals(rate: float, duration_s: float, seed=0, bursty: dict | None = None) -> list[float]:
    """Arrival timestamps in seconds. Bursty: alternate on (rate*peak) / off (rate/peak) phases."""
    rng = np.random.default_rng(seed)
    t, out = 0.0, []
    while t < duration_s:
        r = rate
        if bursty:
            period = bursty["on_s"] + bursty["off_s"]
            on = (t % period) < bursty["on_s"]
            r = rate * bursty["peak_factor"] if on else rate / bursty["peak_factor"]
        t += rng.exponential(1.0 / r)
        if t < duration_s:
            out.append(t)
    return out


FAULTS = ["sig", "zk", "policy", "stale", "replay", "absent"]


def fault_plan(count: int, rho: float, seed=0) -> list[str]:
    """Per-request tamper tag ('' = valid); a fraction rho is invalid, faults drawn uniformly."""
    rng = random.Random(seed)
    return [rng.choice(FAULTS) if rng.random() < rho else "" for _ in range(count)]
