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
A system is saturated at a rate when decided/offered (measurement window, valid requests; decided = any
final outcome, so a protocol-level rejection such as S1's one-redaction-per-block is not mistaken for
overload) drops below 1 - saturation_tolerance; its higher rates are skipped and recorded as such.
Goodput (finalized redactions/s) is reported separately.
"""

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

    def client(i):
        for r in ds.trace[i :: x["client_threads"]]:
            if stop.is_set():
                return
            delay = r.arrival_s - now()
            if delay > 0:
                time.sleep(delay)
            p = prepare(s, r)  # the requester proves against the state at its arrival time
            stamp[r.seq]["submit"] = now()
            admit.put((r, p))

    def revalidator():
        """Stale requests are returned to their requester, which re-proves and resubmits (Phases 4/5).
        Latency keeps running from the ORIGINAL submission."""
        while True:
            r = revalq.get()
            if r is None:
                return
            p = prepare(s, r)
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
    s.teardown()

    # rows + decisions over the measurement cohort: valid requests whose ARRIVAL falls in the window
    w0 = x["warmup_s"]
    offered = finalized = decided = on_time = 0
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
            finalized += status == "finalized"
            decided += status in ("finalized", "rejected", "failed")
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
        f"submitted-in-window={client:.3f}  decided/offered={ratio:.3f}  goodput={finalized / x['duration_s']:.1f}/s"
    )
    return ratio, client


def run(cfg, out):
    x = cfg["experiment"]
    tol, patience = x["saturation_tolerance"], x["saturation_patience"]
    for key in system_keys(cfg):  # one run per point (no repetitions): every request of the run is a sample
        if not out.begin(key):
            continue
        saturated = 0
        for rate in x["rates"]:  # rate sweep at the default skew
            ratio, client = run_point(cfg, key, rate, cfg["workload"]["zipf_s"], out, "rate")
            if client < 1 - tol:
                out.note(
                    f"{x['id']} {key}: requesters submitted only {client:.0%} of the {rate} req/s "
                    "window on time — client-bound, not system-bound; higher rates skipped"
                )
                break
            # one point below 1 - tol does not end the sweep: VeRedact-PQ's batch-version freshness can tip a
            # point into a revalidation storm by chance (pilot: same point 17-61 % or 100 % decided)
            saturated = saturated + 1 if ratio < 1 - tol else 0
            if saturated >= patience:
                out.note(
                    f"{x['id']} {key}: saturated at {patience} consecutive rates up to {rate} req/s; higher skipped"
                )
                break
        for zs in x["zipf_sweep"]:  # skew sweep at a fixed rate
            run_point(cfg, key, x["zipf_rate"], zs, out, "skew")
        out.end()
