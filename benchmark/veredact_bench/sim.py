"""Discrete-event pipeline for Exp. 1 (end-to-end latency and throughput).

Every protocol step is *really executed* when its event fires; its measured wall time becomes the
service time in simulated time. Resources: a pool of VPS validation workers, one committee
authorization server, one execution server; finalization happens at the next block boundary
(Besu QBFT block period) plus network latency. Latency = finalization - original submission.
Requests excluded as stale/conflicting are returned for revalidation (their latency keeps growing).
"""
import heapq
import itertools
import time

from .protocol.veredact import Rejection, VeRedactPQ


def _timed(fn, *a):
    t = time.perf_counter()
    out = fn(*a)
    return out, time.perf_counter() - t


class Pipeline:
    def __init__(self, scheme, targets, rate, block_period_s=2.0, net_ms=10.0, vps_workers=4, requesters=16):
        self.s = scheme
        self.is_vr = isinstance(scheme, VeRedactPQ)
        self.targets, self.rate = targets, rate
        self.P, self.net = block_period_s, net_ms / 1000
        self.vps_free = [0.0] * vps_workers
        self.auth_free = self.exec_free = 0.0
        self.events, self.seq = [], itertools.count()
        self.pending = []  # validated, waiting for ABRRR
        self.batch_deadline = None
        self.done = []  # (t_submit, t_final)
        self.rejected = 0
        self.adaptations = 0
        self.requesters = requesters
        self._k = 0

    def push(self, t, kind, payload=None):
        heapq.heappush(self.events, (t, next(self.seq), kind, payload))

    def finalize_time(self, t):
        return (int((t + self.net) / self.P) + 1) * self.P

    # -------------------------------------------------------------- stages
    def _submit(self, now, t0, tid):
        self._k += 1
        R = self.s.make_request(self._k % self.requesters, tid, b"redacted-%d" % self._k)
        i = min(range(len(self.vps_free)), key=self.vps_free.__getitem__)
        start = max(now, self.vps_free[i])
        res, dur = _timed(self.s.validate, R)
        self.vps_free[i] = start + dur
        self.push(start + dur, "validated", (t0, tid, res, R))

    def _on_validated(self, now, t0, tid, res, R):
        if self.is_vr:
            if isinstance(res, Rejection):
                self.rejected += 1
                return
            res.t_submit = t0
            self.pending.append(res)
            self._maybe_close(now)
        else:  # baselines: per-request authorize + execute
            if res is None:
                self.rejected += 1
                return
            start = max(now, self.auth_free)
            ok, d1 = _timed(self.s.authorize, R)
            self.auth_free = start + d1
            if not ok:
                self.rejected += 1
                return
            start = max(self.auth_free, self.exec_free)
            _, d2 = _timed(self.s.execute, R)
            self.exec_free = start + d2
            self.adaptations += 1
            self.done.append((t0, self.finalize_time(self.exec_free)))

    def _maybe_close(self, now, timeout=False):
        s = self.s
        target = s.target_batch_size(self.rate)
        if not self.pending:
            return
        if len(self.pending) >= target or (timeout and s.batching != "fixed"):
            batch, self.pending = self.pending[:target], self.pending[target:]
            self.batch_deadline = None
            self._run_batch(now, batch)
            if self.pending:
                self._maybe_close(now)
        elif self.batch_deadline is None and s.batching != "fixed":
            self.batch_deadline = now + s.T_max_ms / 1000
            self.push(self.batch_deadline, "timeout")

    def _run_batch(self, now, batch):
        s = self.s
        start = max(now, self.auth_free)
        auth, d1 = _timed(s.authorize, batch)
        self.auth_free = start + d1
        members = auth.members if auth else []
        retry = [v for v in batch if v not in members]
        if auth:
            start = max(self.auth_free, self.exec_free)
            before = s.c.counts["T_CB"]
            rrs, d2 = _timed(s.execute, auth)
            self.exec_free = start + d2
            self.adaptations += s.c.counts["T_CB"] - before
            ok = {rr.RID for rr in rrs}
            tf = self.finalize_time(self.exec_free)
            for v in members:
                if v.RID in ok:
                    self.done.append((v.t_submit, tf))
                else:
                    retry.append(v)
        for v in retry:  # stale / conflicting -> revalidate with the current state
            self.push(max(self.exec_free, now), "resubmit", (v.t_submit, v.req.TID))

    # -------------------------------------------------------------- run
    def run(self, arrivals):
        for t in arrivals:
            self.push(t, "arrival", (t, self.targets.pick()))
        while self.events or (self.is_vr and self.pending):
            if not self.events:  # drain partial batch at end of run (Fixed-Batch never times out)
                batch, self.pending = self.pending, []
                self._run_batch(max(self.auth_free, self.exec_free), batch)
                continue
            now, _, kind, p = heapq.heappop(self.events)
            if kind in ("arrival", "resubmit"):
                self._submit(now, *p)
            elif kind == "validated":
                self._on_validated(now, *p)
            elif kind == "timeout":
                if self.batch_deadline is not None and now >= self.batch_deadline - 1e-12:
                    self._maybe_close(now, timeout=True)
        return self

    def results(self, duration_s):
        lat = [tf - t0 for t0, tf in self.done]
        # throughput over the makespan: a saturated scheme finishes late, which lowers its rate
        makespan = max([duration_s] + [tf for _, tf in self.done])
        return {
            "finalized": len(self.done),
            "throughput": len(self.done) / makespan,
            "makespan_s": makespan,
            "latencies": lat,
            "rejected": self.rejected,
            "adapt_per_1000": 1000 * self.adaptations / max(1, len(self.done)),
        }
