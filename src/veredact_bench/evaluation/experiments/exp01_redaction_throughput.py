"""Exp. 1 — redaction latency & throughput (manuscript Fig. 3). Real time, open loop, every system.

Pipeline (identical for every system; only the Scheme behind it changes):
  clients   [experiment.client_threads] requester threads: at the trace's Poisson arrival time, prepare (sign +
            prove for VeRedact-PQ; nothing for baselines) and submit. Submission is stamped AFTER prepare;
            a client that falls behind is recorded (client_lag_ms, achieved offered rate), not hidden.
            Stale requests (Phase 3 freshness, Phase 4/5 stale/conflict) go back to a requester thread,
            are re-proved and resubmitted, as the manuscript specifies ("returned for revalidation").
  workers   [veredact.vps_workers] threads call authorize() (Phase 3 / the baseline's authorization).
  executor  one thread forms batches — VeRedact: B_e* from ABRRR, flushed at
            B_e* or T_max; baselines: 1 (their papers redact per request) — and calls redact().
  finality  VeRedact returns a ledger Future; its receipt time is the request's completion. Baselines
            block on the receipt inside redact().
Latency = finalized - submitted. Crypto and ledger time stay separate columns.
Every system runs EVERY rate (author rule 2026-10-05: no figure line may end early). A point is noted as
saturated when decided/offered (window arrivals, valid requests; decided = any final outcome, so a
protocol-level rejection such as S1's one-redaction-per-block is not mistaken for overload) or the on-time
submission fraction drops below 1 - saturation_tolerance; the note never skips a rate.
Throughput = redactions finalized during the window / its length (summaries._exp01).
"""

import multiprocessing
import os
import queue
import threading
import time

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import (
    RWLock,
    authorize,
    capability_fields,
    is_veredact,
    open_system,
    prepare,
    revalidate,
)
from veredact_bench.methods.registry import system_keys
from veredact_bench.methods.scheme import RedactionOutcome
from veredact_bench.utils import cpus

_REQ = None  # the VeRedact-PQ system a forked requester process proves for (static credentials and keys)


def _req_init(requester_cpus):
    if requester_cpus:
        os.sched_setaffinity(0, requester_cpus)


def _req_job(job):
    """Requester process: PQZK proof + PQ signature for one request (requester side, excluded from T_val)."""
    return _REQ.p.requester_work(job)


def run_point(cfg, key, rate, zipf_s, out, sweep):
    x = cfg["experiment"]
    window = x["warmup_s"] + x["duration_s"]
    ds = build_dataset(cfg, n_requests=max(1, int(rate * window)), rate=rate, zipf_s=zipf_s)
    out.dataset(ds.dataset_id)
    s = open_system(cfg, key, ds)
    lock, admit, validated, revalq = RWLock(), queue.Queue(), queue.Queue(), queue.Queue()
    stamp = {r.seq: {} for r in ds.trace}
    batch_no = [0]  # executor-side batch counter (rows of one batch share batch_id / batch_adaptations)
    stop = threading.Event()
    t0 = time.perf_counter() + 0.5  # clients start preparing now; arrivals are relative to t0
    now = lambda: time.perf_counter() - t0

    pin = x.get("cpu_pin")  # diagnostics only: {"requesters": [cpus], "system": [cpus]} (Linux)

    def pin_to(part):
        if pin and hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(threading.get_native_id(), pin[part])

    # audit A3: requester proving (VeRedact-PQ only: the baselines' requesters do no proving) runs in forked
    # processes on their own physical cores, so it competes neither for the system's cores nor for its GIL
    req_cpus, sys_cpus = cpus.split(x["requester_cores"])
    pool = None
    if is_veredact(s) and x["requester_cores"] > 0:
        global _REQ
        _REQ = s  # inherited by fork: credential registry and keys are static during the run
        pool = multiprocessing.get_context("fork").Pool(
            x["requester_processes"], initializer=_req_init, initargs=(req_cpus,)
        )
    if sys_cpus:
        os.sched_setaffinity(0, sys_cpus)  # this thread; every thread started below inherits it

    def requester(r):
        """The request as its requester sends it, proved against the state at THIS moment."""
        if pool is None:
            return prepare(s, r)
        R, job = s.prepare_begin(r)  # reads the live batch version (cheap: hashing only)
        if job is not None:
            R.proof, R.sigma_R = pool.apply(_req_job, (job,))
        return R

    def client(i):
        pin_to("requesters")
        for r in ds.trace[i :: x["client_threads"]]:
            if stop.is_set():
                return
            delay = r.arrival_s - now()
            if delay > 0:
                time.sleep(delay)
            p = requester(r)  # the requester proves against the state at its arrival time
            stamp[r.seq]["submit"] = stamp[r.seq]["proved"] = now()
            admit.put((r, p))

    def revalidator():
        """Stale requests are returned to their requester, which re-proves and resubmits (Phases 4/5).
        Latency keeps running from the ORIGINAL submission."""
        pin_to("requesters")
        while True:
            r = revalq.get()
            if r is None:
                return
            p = requester(r)
            stamp[r.seq]["proved"] = now()  # this attempt's proof (staleness window: proved -> auth_done)
            admit.put((r, p))

    def send_back(r):
        st = stamp[r.seq]
        for k in ("exec_start", "exec_done", "batch_size", "batch_id", "batch_adaptations"):
            st.pop(k, None)  # timings describe the request's last attempt (else queue_ms < 0 after a resubmission)
        st.update(status="revalidating", revalidations=st.get("revalidations", 0) + 1)
        revalq.put(r)

    def worker():
        while True:
            item = admit.get()
            if item is None:
                return
            r, p = item
            with lock.read():
                a = authorize(s, r, p)
            stamp[r.seq].update(auth_done=now(), auth_ms=a.crypto_ms, auth_ok=a.ok, reason=a.reason)
            if a.ok:
                validated.put(a)
            elif revalidate(r, RedactionOutcome(r.seq, False, reason=a.reason)):
                send_back(r)
            else:
                stamp[r.seq].update(status="rejected")

    def executor():
        veredact = is_veredact(s)
        t_max = cfg["veredact"]["T_max_ms"] / 1000 if veredact else 0.0
        buf, enq, arrivals = [], [], []  # enq[i] = when buf[i] entered the pending queue Q_e
        # stop = drain window over: requests still queued stay 'unfinished' (a saturated point), and the
        # executor exits so no transaction of this point reaches the ledger after the next point starts
        while not stop.is_set():
            try:
                a = validated.get(timeout=0.005)
                buf.append(a)
                enq.append(now())
                arrivals.append(enq[-1])
            except queue.Empty:
                pass
            if not buf:
                continue
            arrivals[:] = [t for t in arrivals if t > now() - 1.0]  # lambda_hat over the last second
            B = s.p.target_batch_size(len(arrivals)) if veredact else 1
            if len(buf) < B and now() - enq[0] < t_max and not stop.is_set():
                continue  # ABRRR: close at B_e* requests or when the oldest has waited T_max
            batch, buf, enq = buf[:B], buf[B:], enq[B:]
            t_exec = now()
            with lock.write():
                res = s.redact(batch)
            t_done = now()
            batch_no[0] += 1
            for a, o in zip(batch, res.outcomes):
                st = stamp[a.request.seq]
                st.update(
                    exec_start=t_exec,
                    exec_done=t_done,
                    batch_size=len(batch),
                    batch_id=batch_no[0],
                    batch_adaptations=res.ch_adaptations,
                    redact_crypto_ms=res.crypto_ms,
                    redact_ledger_ms=res.ledger_ms,
                    status="pending" if o.ok else "failed",
                    reason=o.reason or st.get("reason", ""),
                )
                if not o.ok and revalidate(a.request, o):
                    send_back(a.request)
                if o.ok and res.finality is None:
                    st.update(final=t_done, status="finalized")
            if res.finality is not None:
                oks = [a.request.seq for a, o in zip(batch, res.outcomes) if o.ok]

                def done(f, oks=oks):
                    t = now()
                    ms, _ = f.result()
                    for q in oks:
                        stamp[q].update(final=t, finality_ledger_ms=ms, status="finalized")

                res.finality.add_done_callback(done)

    clients = [threading.Thread(target=client, args=(i,), daemon=True) for i in range(x["client_threads"])]
    workers = [threading.Thread(target=worker, daemon=True) for _ in range(cfg["veredact"]["vps_workers"])]
    workers_r = [threading.Thread(target=revalidator, daemon=True) for _ in range(x["client_threads"])]
    ex = threading.Thread(target=executor, daemon=True)
    pin_to("system")  # threads inherit the creator's affinity: workers and executor stay on the system cpus
    for th in clients + workers + workers_r + [ex]:
        th.start()
    for th in clients:
        th.join(timeout=max(0.0, window - now()) + x["drain_s"])
    deadline = time.perf_counter() + x["drain_s"]
    while time.perf_counter() < deadline and any(
        v.get("status") in (None, "pending", "revalidating") for v in stamp.values() if "submit" in v
    ):
        time.sleep(0.05)
    stop.set()
    for _ in workers:
        admit.put(None)
    for _ in workers_r:
        revalq.put(None)
    ex.join()  # returns after the batch in progress: the next point's anchor must not share the account
    if pool is not None:
        pool.terminate()
        pool.join()
    if sys_cpus:
        os.sched_setaffinity(0, sum(cpus.physical_cores(), []))  # setup of the next point uses every core
    s.teardown()

    # rows + decisions over the measurement cohort: valid requests whose ARRIVAL falls in the window
    w0 = x["warmup_s"]
    offered = completed = decided = on_time = 0
    for r in ds.trace:
        st = stamp[r.seq]
        status = st.get("status", "unfinished")
        status = (
            status
            if status in ("finalized", "rejected", "failed")
            else ("unfinished" if "submit" in st else "not_submitted")
        )
        in_window = w0 <= r.arrival_s < window
        if in_window and not r.fault:
            offered += 1
            on_time += "submit" in st and st["submit"] < window
            decided += status in ("finalized", "rejected", "failed")
        if status == "finalized" and not r.fault and w0 <= st.get("final", -1) < window:
            completed += 1  # throughput: finalized DURING the window, whatever its arrival (summaries._exp01)
        out.row(
            experiment=x["id"],
            sweep=sweep,
            system=key,
            rate_rps=rate,
            zipf_s=zipf_s,
            seq=r.seq,
            fault=r.fault,
            arrival_s=r.arrival_s,
            submit_s=st.get("submit", ""),
            client_lag_ms=(st["submit"] - r.arrival_s) * 1000 if "submit" in st else "",
            # last attempt: its proof's age when the VPS validated it (stale if its batch changed meanwhile)
            proof_age_ms=(st["auth_done"] - st["proved"]) * 1000
            if st.get("auth_done", -1) >= st.get("proved", 0)  # re-proved but never re-validated: no value
            else "",
            in_window=int(in_window),
            status=status,
            reason=st.get("reason", ""),
            auth_ms=st.get("auth_ms", ""),
            revalidations=st.get("revalidations", 0),
            batch_size=st.get("batch_size", ""),
            batch_id=st.get("batch_id", ""),
            batch_adaptations=st.get("batch_adaptations", ""),
            queue_ms=(st["exec_start"] - st["auth_done"]) * 1000 if "exec_start" in st else "",
            redact_crypto_ms=st.get("redact_crypto_ms", ""),
            redact_ledger_ms=st.get("redact_ledger_ms", ""),
            finality_ledger_ms=st.get("finality_ledger_ms", ""),
            latency_ms=(st["final"] - st["submit"]) * 1000 if "final" in st else "",
            setup_s=s.setup_s,
            **capability_fields(s),
        )
    client = on_time / offered if offered else 1.0
    ratio = decided / offered if offered else 1.0
    out.log.info(
        f"  {key:28s} rate={rate:<6} s={zipf_s:<4}  offered={offered / x['duration_s']:7.1f}/s  "
        f"submitted-in-window={client:.3f}  decided/offered={ratio:.3f}  throughput={completed / x['duration_s']:.1f}/s"
    )
    return ratio, client


def run(cfg, out):
    x = cfg["experiment"]
    tol = x["saturation_tolerance"]
    _, sys_cpus = cpus.split(x["requester_cores"])
    if sys_cpus and cfg["ledger"]["backend"] == "besu":
        cpus.pin_besu(sys_cpus)  # the validators belong to the system side (audit A3)
    for key in system_keys(cfg):  # one run per point (no repetitions): every request of the run is a sample
        if not out.begin(key):
            continue
        for rate in x["rates"]:  # rate sweep at the default skew: every rate, for every system
            ratio, client = run_point(cfg, key, rate, cfg["workload"]["zipf_s"], out, "rate")
            # noted, never skipped: requesters also re-prove every stale request (Phases 4/5), so under a
            # revalidation storm the on-time fraction falls together with decided/offered
            if ratio < 1 - tol or client < 1 - tol:
                out.note(f"{x['id']} {key}: saturated at {rate} req/s (decided {ratio:.0%}, on time {client:.0%})")
        for zs in x["zipf_sweep"]:  # skew sweep at a fixed rate
            run_point(cfg, key, x["zipf_rate"], zs, out, "skew")
        out.end()
    if sys_cpus and cfg["ledger"]["backend"] == "besu":
        cpus.pin_besu(None)  # later experiments use every cpu
