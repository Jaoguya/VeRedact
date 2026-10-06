"""Requester prover service for Exp. 1 (audit A4): run on each prover host.
    VRPQ_PROVER_KEY=<shared secret> VRPQ_SIG_BACKEND=oqs .venv/bin/python scripts/prover_service.py --port 7700
One worker process per core (single-core STARK proofs, as on a requester device). See evaluation/provers.py."""

import argparse
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from multiprocessing.connection import Listener

_STATE = {}


def _init(b):
    from veredact_bench.methods.veredact.crypto.pqsig import load_pqsig
    from veredact_bench.methods.veredact.crypto.pqzk_stark import PolicySTARK, ZKParams

    _STATE["zk"] = PolicySTARK(ZKParams(**b["params"]), b["requesters"], b["seed"], b["now_s"])
    _STATE["sig"], _STATE["sks"] = load_pqsig(), b["sks"]


def _work(job):
    prove, signer, h = job
    proof = _STATE["zk"].prove(*prove) if prove else b""
    return proof, _STATE["sig"].sign(_STATE["sks"][signer], h)


def _check(b):
    from veredact_bench.methods.veredact.crypto.pqzk_stark import PolicySTARK, ZKParams

    return PolicySTARK(ZKParams(**b["params"]), b["requesters"], b["seed"], b["now_s"]).root == b["root"]


def serve(conn, workers):
    pool, lock = None, threading.Lock()
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            break
        if msg[0] == "init":
            if pool:
                pool.shutdown(cancel_futures=True)
            if not _check(msg[1]):
                conn.send(("error", "rebuilt credential registry root differs from the system's"))
                continue
            pool = ProcessPoolExecutor(workers, initializer=_init, initargs=(msg[1],))
            conn.send(("ready", workers))
        elif msg[0] == "job":
            _, jid, job = msg

            def done(f, jid=jid):
                proof, sig = f.result()
                with lock:
                    conn.send(("done", jid, proof, sig))

            pool.submit(_work, job).add_done_callback(done)
        elif msg[0] == "close":
            break
    if pool:
        pool.shutdown(cancel_futures=True)
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7700)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    with Listener(("0.0.0.0", a.port), authkey=os.environ["VRPQ_PROVER_KEY"].encode()) as ls:
        print(f"prover service on :{a.port} with {a.workers} workers", flush=True)
        while True:
            threading.Thread(target=serve, args=(ls.accept(), a.workers), daemon=True).start()


if __name__ == "__main__":
    main()
