"""Shared runner machinery. Every experiment drives systems ONLY through Scheme (scheme.py) + registry."""

import dataclasses
import threading
import time

from veredact_bench.methods.registry import make
from veredact_bench.methods.scheme import AuthCost, NotSupported


class RWLock:
    """Readers = authorization workers, writer = the executor. Applied identically to every system: no
    scheme's authorize() may read state while its redact() is half-way through changing it.

    Writer-preferring: once the executor waits, new readers wait too. The earlier reader-preferring lock
    starved the executor whenever authorizations overlapped continuously (pilot 2026-10-04: S1 at 250 req/s,
    52 ms authorizations on 8 workers, authorized 4,865 requests and executed none)."""

    def __init__(self):
        self._c = threading.Condition()
        self._readers, self._writing, self._writers_waiting = 0, False, 0

    def read(self):
        return _Guard(self._acquire_r, self._release_r)

    def write(self):
        return _Guard(self._acquire_w, self._release_w)

    def _acquire_r(self):
        with self._c:
            while self._writing or self._writers_waiting:
                self._c.wait()
            self._readers += 1

    def _release_r(self):
        with self._c:
            self._readers -= 1
            if self._readers == 0:
                self._c.notify_all()

    def _acquire_w(self):
        with self._c:
            self._writers_waiting += 1
            while self._writing or self._readers:
                self._c.wait()
            self._writers_waiting -= 1
            self._writing = True

    def _release_w(self):
        with self._c:
            self._writing = False
            self._c.notify_all()


class _Guard:
    def __init__(self, a, r):
        self.a, self.r = a, r

    def __enter__(self):
        self.a()

    def __exit__(self, *exc):
        self.r()


def open_system(cfg: dict, key: str, dataset, committee_n: int | None = None):
    s = make(cfg, key, committee_n)
    t = time.perf_counter()
    s.setup(dataset)
    s.setup_s = time.perf_counter() - t
    return s


def is_veredact(s) -> bool:
    return hasattr(s, "prepare")


def prepare(s, req):
    """Requester-side work (sign + prove for VeRedact-PQ). Never inside an authorization timer."""
    return s.prepare(req) if is_veredact(s) else None


def authorize(s, req, prepared=None):
    return s.authorize(req, prepared) if is_veredact(s) else s.authorize(req)


def auth_cost_fields(s) -> dict:
    try:
        return {f"cost_{k}": v for k, v in dataclasses.asdict(s.auth_cost()).items()}
    except NotSupported:
        return {f"cost_{f.name}": "" for f in dataclasses.fields(AuthCost)}


def capability_fields(s) -> dict:
    return {f"cap_{k}": int(v) for k, v in dataclasses.asdict(s.capabilities()).items()}


def build_history(s, trace, batch_size: int) -> dict:
    """Closed-loop, untimed: redact the trace in batches of batch_size until every valid request is either
    redacted or rejected for a non-freshness reason (a stale request is re-prepared and resubmitted, as its
    requester would). Returns outcome counts. Used to create audit/gas histories, never to report latency.
    Ledger finality is awaited once at the end: outcomes (and so revalidation) never depend on a receipt,
    and every system anchors pipelined, so the history costs crypto time, not one block per chunk."""
    counts = {"redacted": 0, "rejected": 0, "resubmitted": 0}
    in_flight = []
    pending = list(trace)
    while pending:
        retry = []
        for i in range(0, len(pending), batch_size):
            chunk = pending[i : i + batch_size]
            auths = [authorize(s, r, prepare(s, r)) for r in chunk]
            res = s.redact(auths)
            in_flight.append(res)
            for r, o in zip(chunk, res.outcomes):
                if o.ok:
                    counts["redacted"] += 1
                elif revalidate(r, o):
                    retry.append(r)
                else:
                    counts["rejected"] += 1
        # a stale retry is only productive if the previous round redacted something
        if retry and len(retry) == len(pending):
            counts["rejected"] += len(retry)
            break
        counts["resubmitted"] += len(retry)
        pending = retry
    for res in in_flight:
        res.wait()
    return counts


def revalidate(req, outcome) -> bool:
    """Manuscript Phases 4/5: stale or conflicting requests are "returned for revalidation" — the requester
    re-proves against the current state and resubmits. Injected faults are never resubmitted."""
    return not req.fault and (outcome.stale or outcome.reason.startswith("freshness:"))
