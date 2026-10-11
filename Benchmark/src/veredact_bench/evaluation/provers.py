"""Remote requester provers for Exp. 1 (audit A4): requesters are separate devices, so their PQZK proving and
PQ signing run on separate machines, never on the system under test's cores.

  service   scripts/prover_service.py on each prover host: one process per core; per Exp. 1 point it receives
            a bundle (credential-registry parameters + requester signing keys) and rebuilds exactly the
            system's requester state (PolicySTARK is seeded: same seed, requester count and construction time
            give the same registry and root); then it answers ("job", id, job) with ("done", id, proof, sig).
  client    RemoteProvers below: connects to every host, sends the bundle, spreads jobs over the hosts by
            outstanding work and calls back when a proof arrives. Requests are still BUILT on the system at
            arrival time (live batch version, hashing only): only the requester's expensive work travels.
Transport: multiprocessing.connection (pickle) with an HMAC authkey (VRPQ_PROVER_KEY), private VPC addresses only.
"""

import collections
import itertools
import os
import threading
from dataclasses import asdict
from multiprocessing.connection import Client


def bundle(scheme) -> dict:
    """Everything a prover host needs to act as this point's requesters."""
    zk = scheme.crypto.zk
    return {
        "params": asdict(zk.p),
        "requesters": zk.requesters,
        "seed": zk.seed,
        "now_s": zk.now_s,
        "sks": [r.sk for r in scheme.ledger.requesters],
        "root": zk.root,  # checked by the service after rebuilding
    }


class RemoteProvers:
    """Credit-based dispatch: a host gets at most `workers` jobs in flight. A request waiting for a free
    prover is BUILT (live batch version read) only when it is dispatched, so its proof is computed right after
    the state it binds — as on a requester's own device. Queuing proofs behind busy provers would bind them to
    versions that are stale by the time they are proved (observed on loopback, 2026-10-06)."""

    def __init__(self, addresses: list[str], scheme):
        key = os.environ["VRPQ_PROVER_KEY"].encode()
        self._conns, self._load, self._cap, self._lock = [], [], [], threading.Lock()
        self._cb, self._ids, self._pending = {}, itertools.count(), collections.deque()
        b = bundle(scheme)
        for a in addresses:
            host, port = a.rsplit(":", 1)
            c = Client((host, int(port)), authkey=key)
            c.send(("init", b))
            kind, info = c.recv()
            if kind != "ready":
                raise RuntimeError(f"prover {a}: {info}")
            self._conns.append((c, threading.Lock()))
            self._load.append(0)
            self._cap.append(int(info))  # the host's worker processes
        self._readers = [
            threading.Thread(target=self._read, args=(i,), daemon=True, name=f"prover-rx-{i}")
            for i in range(len(self._conns))
        ]
        for t in self._readers:
            t.start()

    def submit(self, make_job, callback) -> None:
        """make_job() builds the request and returns its job at dispatch time; callback(proof, sig) runs on a
        reader thread when the proof arrives. Never blocks."""
        with self._lock:
            self._pending.append((make_job, callback))
        self._pump()

    def _pump(self) -> None:
        while True:
            with self._lock:
                free = [i for i in range(len(self._load)) if self._load[i] < self._cap[i]]
                if not free or not self._pending:
                    return
                i = min(free, key=lambda h: self._load[h] / self._cap[h])
                make_job, cb = self._pending.popleft()
                self._load[i] += 1
                jid = next(self._ids)
                self._cb[jid] = (i, cb)
            job = make_job()  # reads the live state now: the proof starts as soon as it arrives
            c, lk = self._conns[i]
            with lk:
                c.send(("job", jid, job))

    def _read(self, i):
        c, _ = self._conns[i]
        while True:
            try:
                msg = c.recv()
            except (EOFError, OSError, TypeError):  # TypeError: the connection was closed under recv
                return
            if msg[0] != "done":
                continue
            _, jid, proof, sig = msg
            with self._lock:
                host, cb = self._cb.pop(jid)
                self._load[host] -= 1
            cb(proof, sig)
            self._pump()

    def close(self):
        with self._lock:
            self._pending.clear()
        for c, lk in self._conns:
            with lk:
                try:
                    c.send(("close",))
                except OSError:
                    pass
            c.close()
