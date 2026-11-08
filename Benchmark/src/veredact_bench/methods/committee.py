"""Committee timing, the same for every threshold scheme (fairness fix, #5 step 2 / #13).

The t committee members of VeRedact-PQ and Schemes [1] and [27] are separate machines that talk over the
network. The harness runs them in one process, one after another, so it used to SUM their work and model no
message delay at all: that charged VeRedact-PQ 5 x 18 ms of PQCH shares where it would wait for the slowest share,
and gave Scheme [27]'s two message rounds per redaction for free. CommitteeClock fixes both, for every scheme alike:

  members   each member's work is timed on its own; a committee step's CRYPTO time counts the slowest member
            (the others run concurrently on their own machines);
  network   each message round waits, in real wall time, until (slowest member + message delay) has passed
            since the round started -- the same delay as between the Besu validators (ledger.netem_delay_ms).
            The wait is network time, reported separately, never added to crypto time.

Members still run in turn here, so when their sum already exceeds slowest + delay no extra wait is added: the
wall time is then conservative (longer than on separate machines) for schemes with heavy members.

Usage inside a timed section:  outs = self.committee.round([lambda: work_1(), ...]); then
    credit_s, net_ms = self.committee.take();  crypto_ms = (elapsed_s - credit_s) * 1000
"""

import threading
import time


class CommitteeClock:
    def __init__(self, delay_ms: float = 10.0, parallel: bool = True, clock=time.perf_counter, sleep=time.sleep):
        self.delay_ms, self.parallel = float(delay_ms), parallel
        self._clock, self._sleep = clock, sleep
        # per thread: Scheme [1] authorizes in several VPS worker threads at once, and each caller subtracts
        # only the credit of its own timed section
        self._local = threading.local()
        self.rounds = 0  # message rounds so far (all threads)
        self._lock = threading.Lock()

    def __getstate__(self):  # saved histories (evaluation/history_cache.py) pickle the scheme
        return {k: v for k, v in self.__dict__.items() if k not in ("_local", "_lock", "_clock", "_sleep")}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._local, self._lock = threading.local(), threading.Lock()
        self._clock, self._sleep = time.perf_counter, time.sleep

    @classmethod
    def from_cfg(cls, cfg: dict) -> "CommitteeClock":
        c = cfg.get("committee", {})
        delay = c.get("message_delay_ms", cfg.get("ledger", {}).get("netem_delay_ms", 0))
        return cls(delay_ms=delay, parallel=c.get("parallel_members", True))

    def round(self, members: list) -> list:
        """One committee message round: every member's work, then the round trip."""
        start = self._clock()
        out, slowest = [], 0.0
        for work in members:
            t0 = self._clock()
            out.append(work())
            slowest = max(slowest, self._clock() - t0)
        spent = self._clock() - start
        with self._lock:
            self.rounds += 1
        if not self.parallel:  # off switch: the old harness exactly -- members summed, no message delay
            self._local.last_step_s = spent
            return out
        wait = max(0.0, slowest + self.delay_ms / 1000 - spent)
        waited = 0.0
        if wait > 0:
            w0 = self._clock()
            self._sleep(wait)
            waited = self._clock() - w0  # what really passed: an oversleep must not land in crypto time
        # removed from crypto time: the other members' share of the serial run, and the network wait
        loc = self._local
        loc.credit_s = getattr(loc, "credit_s", 0.0) + (spent - slowest) + waited
        loc.net_ms = getattr(loc, "net_ms", 0.0) + self.delay_ms
        loc.last_step_s = slowest
        return out

    def last_slowest_ms(self) -> float:
        """A committee step's crypto time in this thread's last round: the slowest member (off switch: the sum)."""
        return getattr(self._local, "last_step_s", 0.0) * 1000

    def take(self) -> tuple[float, float]:
        """(seconds to subtract from the caller's crypto timer, network ms) since the last take."""
        loc = self._local
        out = (getattr(loc, "credit_s", 0.0), getattr(loc, "net_ms", 0.0))
        loc.credit_s = loc.net_ms = 0.0
        return out
