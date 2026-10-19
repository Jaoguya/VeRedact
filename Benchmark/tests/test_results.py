"""Results layout, idempotency and a tiny end-to-end run through the real runner."""

import copy
import json

from veredact_bench.evaluation.experiments import RUNNERS
from veredact_bench.evaluation.results import RunWriter
from veredact_bench.utils.config import load

FILES = {"rows.csv", "metrics.json", "config_resolved.yaml", "run_info.json", "run.log"}


def _cfg(tmp_path, exp):
    c = copy.deepcopy(load("smoke", exp))
    c["output"]["dir"] = str(tmp_path)  # absolute: results go to the test's temp dir
    return c


def test_writer_layout_skip_and_force(tmp_path):
    cfg = _cfg(tmp_path, "exp00_primitives")
    w = RunWriter(cfg)
    assert w.begin("S27")
    w.row(system="S27", symbol="T_H", instantiation="x", sample=0, ms=1.0)
    w.end()
    d = tmp_path / "exp00_primitives" / "S27" / "smoke"
    assert {p.name for p in d.iterdir()} == FILES
    assert json.loads((d / "metrics.json").read_text())["rows"] == 1
    assert not RunWriter(cfg).begin("S27")  # done: skipped
    w2 = RunWriter(cfg, force=True)
    assert w2.begin("S27")  # forced: folder replaced
    assert not (d / "metrics.json").exists()
    w2.end()


def test_tiny_end_to_end_run(tmp_path):
    cfg = _cfg(tmp_path, "exp00_primitives")
    cfg["experiment"]["systems"], cfg["experiment"]["samples_per_point"] = ["S27"], 2
    RUNNERS["exp00_primitives"](cfg, RunWriter(cfg))
    d = tmp_path / "exp00_primitives" / "S27" / "smoke"
    m = json.loads((d / "metrics.json").read_text())
    assert {p.name for p in d.iterdir()} == FILES
    assert all(v["n"] == 2 and v["median"] > 0 for v in m["points"].values())


def test_paper_artifacts_show_only_the_paper_schemes(monkeypatch):
    from veredact_bench.reporting import figures, style, tables

    keys = ["veredact", "S98", "S1", "S13", "S27", "S34", "S99"]  # S98: a method the paper does not compare
    monkeypatch.setattr(figures, "_all_metrics", lambda exp, tier: {k: {"points": {}} for k in keys})
    assert list(figures.metrics("exp01_redaction_throughput", "smoke")) == list(style.PAPER_METHODS)
    assert tables.ORDER == ["veredact", "S1", "S13", "S27", "S34", "S99"]


def test_gas_figure_never_draws_a_baseline_against_the_batch_axis(monkeypatch, tmp_path):
    """Fig. 7: (a) one bar per baseline + VeRedact-PQ at m = 1 and at its default batch; (b) only VeRedact-PQ
    against m, the cheapest baseline as one reference line (baselines have no batching)."""
    from veredact_bench.reporting import figures, style

    def fake(exp, tier):  # two batch sizes per scheme at the default skew, as Exp. 5 records them
        pts = {f"zipf_s=0.8|batch_size={b}": {"gas_per_redaction": 1000.0 + b} for b in (1, 8)}
        return {k: {"points": pts} for k in ("veredact", "S1", "S13", "S27", "S34")}

    monkeypatch.setattr(figures, "_all_metrics", fake)
    monkeypatch.setattr(figures, "OUT", tmp_path)
    cfg = {"workload": {"zipf_s": 0.8}, "veredact": {"reference_batch": 8}}
    monkeypatch.setattr(figures, "load", lambda tier, exp: cfg)
    drawn = {}
    monkeypatch.setattr(
        figures, "_save", lambda fig, name, w: drawn.update({name: [(len(a.patches), len(a.lines)) for a in fig.axes]})
    )
    style.apply()
    figures.fig_exp5("smoke", [])
    assert drawn["exp5_gas_consumption"] == [(4 + 2, 0), (0, 2)]


def test_exp1_adaptations_count_every_finalized_redaction():
    """pqch_adaptations_per_1000 (metrics only since Fig. 3(c) was removed): a scheme that finalizes nothing
    inside the window still gets an adaptation count."""
    from veredact_bench.evaluation.summaries import _exp01

    def row(seq, in_window, status, batch):
        return dict(
            sweep="skew",
            rate_rps=100,
            zipf_s=0.8,
            seq=seq,
            in_window=in_window,
            fault="",
            status=status,
            batch_id=batch,
            batch_adaptations=1,
            latency_ms=10.0,
            submit_s=1.0,
            arrival_s=0.5,
        )

    rows = [row(1, 0, "finalized", 1), row(2, 0, "finalized", 2), row(3, 1, "unfinished", "")]
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 20, "warmup_s": 10}}).values()
    assert pt["finalized"] == 0 and pt["pqch_adaptations_per_1000"] == 1000.0


def test_exp1_throughput_counts_redactions_finalized_during_the_window():
    """Throughput = finalized DURING [warmup, warmup+duration) / duration, whatever the arrival time: a backlog
    request finalized inside the window counts, a window request finalized in the drain does not."""
    from veredact_bench.evaluation.summaries import _exp01

    def row(seq, arrival_win, submit_s, latency_ms):
        return dict(
            sweep="rate",
            rate_rps=100,
            zipf_s=0.8,
            seq=seq,
            in_window=arrival_win,
            fault="",
            status="finalized",
            batch_id=seq,
            batch_adaptations=1,
            submit_s=submit_s,
            latency_ms=latency_ms,
            arrival_s=submit_s,
        )

    rows = [row(1, 0, 5.0, 10_000), row(2, 1, 20.0, 1_000), row(3, 1, 25.0, 60_000)]  # done at 15 s, 21 s, 85 s
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    assert pt["completed_in_window"] == 2 and pt["finalized"] == 2  # rows 1+2 vs arrival cohort rows 2+3
    assert abs(pt["throughput_per_s"] - 2 / 60) < 1e-9


def test_exp1_latency_is_end_to_end_and_never_drops_unfinished_requests():
    """Latency = arrival -> finalized over the window's arrivals; a request unfinished at the cutoff enters with
    cutoff - arrival (lower bound), a protocol rejection is excluded. Client-side waiting is included."""
    from veredact_bench.evaluation.summaries import _exp01

    def row(seq, status, arrival, submit="", lat=""):
        return dict(
            sweep="rate",
            rate_rps=100,
            zipf_s=0.8,
            seq=seq,
            in_window=1,
            fault="",
            status=status,
            batch_id="",
            batch_adaptations="",
            arrival_s=arrival,
            submit_s=submit,
            latency_ms=lat,
            cutoff_s=100.0,
        )

    rows = [
        row(1, "finalized", 10.0, 12.0, 1_000),  # 2 s client wait + 1 s system: 3 s end to end
        row(2, "unfinished", 20.0, 21.0),  # censored: >= 80 s
        row(3, "not_submitted", 60.0),  # censored: >= 40 s
        row(4, "rejected", 30.0, 30.0),  # a decided outcome: not a latency sample
        row(5, "finalized", 50.0, 50.0, 70_000),  # finalized at 120 s, after the cutoff: censored at 50 s
    ]
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    lat = pt["latency_ms"]
    assert lat["n"] == 4 and lat["median"] == 45_000.0
    assert abs(pt["latency_censored_fraction"] - 3 / 4) < 1e-9
    assert pt["latency_p95_lower_bound"] and pt["latency_median_lower_bound"]


def test_exp4_detection_rate_undefined_when_nothing_injected():
    from veredact_bench.evaluation.summaries import _exp04

    rows = [
        dict(
            n_Q=10,
            level="normal",
            inject_fraction=0.01,
            status="ok",
            injected=0,
            detected=0,
            false_rejections=0,
            verify_ms=1.0,
        )
    ]
    (pt,) = _exp04(rows, {}).values()
    assert pt["detection_rate"] is None and pt["injected"] == 0 and pt["false_rejection_rate"] == 0.0


def test_exp2_complete_authorization_counts_both_steps():
    """Fig. 4: per request = per-request step + batch step / m; per batch = m per-request steps + batch step."""
    from veredact_bench.evaluation.summaries import _exp02

    def row(sample, ph3, ph4, m=2):
        return dict(
            committee_n=4,
            batch_size=m,
            sample=sample,
            phase3_ms=ph3,
            phase4_batch_ms=ph4,
            auth_per_request_ms=1.0,
            batch_total_ms=1.0,
            auth_ok=1,
        )

    (v,) = _exp02([row(0, 1.0, 4.0), row(0, 3.0, 4.0)], {}).values()  # batch protocol: 2 requests + 4 ms
    assert v["auth_complete_per_request_ms"]["median"] == 4.0 and v["auth_complete_per_batch_ms"]["median"] == 8.0
    (b,) = _exp02([row(0, 1.0, ""), row(0, 3.0, "")], {}).values()  # no batch protocol: the m authorizations
    assert b["auth_complete_per_request_ms"]["median"] == 2.0 and b["auth_complete_per_batch_ms"]["median"] == 4.0


def test_exp2_s99_amortized_is_its_batch_protocol(tmp_path):
    """S99 has its own batch protocol (aggregation + Eq. 13): amortized = batch / m, like VeRedact-PQ Phase 4."""
    import csv

    cfg = _cfg(tmp_path, "exp02_authorization_latency")
    x = cfg["experiment"]
    x["systems"], x["committee_sizes"], x["batch_sizes"], x["samples_per_point"] = ["S99"], [4], [1, 4], 1
    RUNNERS["exp02_authorization_latency"](cfg, RunWriter(cfg))
    with open(tmp_path / "exp02_authorization_latency" / "S99" / "smoke" / "rows.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["auth_ok"] == "1" for r in rows)
    for r in rows:
        assert abs(float(r["auth_per_request_ms"]) - float(r["phase4_batch_ms"]) / int(r["batch_size"])) < 1e-9


def test_exp2_veredact_amortized_is_phase4_only(tmp_path):
    """A1: Exp. 2 measures Phase 4. VeRedact-PQ's amortized latency = its batch authorization / m; the Phase 3
    VPS validation is recorded separately (phase3_ms) and not added."""
    import csv

    cfg = _cfg(tmp_path, "exp02_authorization_latency")
    x = cfg["experiment"]
    x["systems"], x["committee_sizes"], x["batch_sizes"], x["samples_per_point"] = ["veredact"], [4], [1, 4], 1
    RUNNERS["exp02_authorization_latency"](cfg, RunWriter(cfg))
    with open(tmp_path / "exp02_authorization_latency" / "veredact" / "smoke" / "rows.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows
    for r in rows:
        assert abs(float(r["auth_per_request_ms"]) - float(r["phase4_batch_ms"]) / int(r["batch_size"])) < 1e-9


def test_exp1_point_leaves_no_thread_behind(tmp_path):
    """A saturated Exp. 1 point leaves a queue backlog; its worker/client/revalidator threads must all have
    exited when run_point returns, or they would load the next point (found in the scale run 2026-10-07)."""
    import threading

    from veredact_bench.evaluation.experiments.exp01_redaction_throughput import run_point

    cfg = _cfg(tmp_path, "exp01_redaction_throughput")
    cfg["experiment"].update(warmup_s=0, duration_s=1, drain_s=1, requester_cores=0)
    out = RunWriter(cfg)
    assert out.begin("S34")
    before = {t.ident for t in threading.enumerate()}
    # S34 authorizes with an ABE decryption (ms each) on 8 VPS workers: 4,000 req/s leaves an admission backlog
    run_point(cfg, "S34", 4000, 0.8, out, "rate")
    left = [t.name for t in threading.enumerate() if t.ident not in before and not t.name.startswith("besu")]
    assert not left, left


def test_anchor_never_waits_forever_for_a_mined_transaction():
    """Full run 2026-10-09: a mined transaction's Future was never resolved (3.5 h hang). _recheck resolves it
    from its receipt, re-sends a transaction the node does not know, and fails one past the timeout."""
    import threading
    import time
    from concurrent.futures import Future

    from veredact_bench.evaluation.anchor import BesuAnchor

    class Eth:
        def __init__(self):
            self.sent = []

        def get_transaction_receipt(self, h):
            if h == b"mined":
                return {"status": 1, "gasUsed": 21000}
            raise ValueError("not found")

        def get_transaction(self, h):
            raise ValueError("not found")

        def send_raw_transaction(self, raw):
            self.sent.append(raw)

    a = object.__new__(BesuAnchor)
    a.w3 = type("W3", (), {"eth": Eth()})()
    a._plock, a.recheck_s, a.timeout_s = threading.Lock(), 30.0, 600.0
    a.recovered = {"late_receipt": 0, "resent": 0, "timed_out": 0}
    now = time.perf_counter()
    futs = {h: Future() for h in (b"mined", b"lost", b"expired", b"fresh")}
    t0 = {b"mined": now - 60, b"lost": now - 60, b"expired": now - 700, b"fresh": now}
    a._pending = {h: (futs[h], t0[h]) for h in futs}
    a._raw = {h: b"raw-" + h for h in futs}
    a._recheck()
    assert futs[b"mined"].result()[1] == 21000  # resolved from its receipt
    assert a.w3.eth.sent == [b"raw-lost"] and not futs[b"lost"].done()  # sent again, still pending
    assert isinstance(futs[b"expired"].exception(), RuntimeError)  # loud failure, not a hang
    assert not futs[b"fresh"].done()  # too young to look up
    assert a.recovered == {"late_receipt": 1, "resent": 1, "timed_out": 1}


def test_repetition_seed_and_folder(monkeypatch):
    """VRPQ_REP=r: seed + (r-1)*1000 (rep 1 = the single-run seed), results in <tier>-repNN."""
    from veredact_bench.utils.config import load, results_tier

    base = load("smoke")["meta"]["seed"]
    monkeypatch.setenv("VRPQ_REP", "3")
    c = load("smoke")
    assert c["meta"]["seed"] == base + 2000 and c["meta"]["rep"] == 3
    assert results_tier("experiment") == "experiment-rep03"
    monkeypatch.setenv("VRPQ_REP", "1")
    assert load("smoke")["meta"]["seed"] == base


def test_aggregate_reps_mean_and_ci():
    import importlib.util

    from veredact_bench.utils.config import REPO_ROOT

    spec = importlib.util.spec_from_file_location("agg", REPO_ROOT / "scripts" / "aggregate_reps.py")
    agg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agg)
    stats = lambda m, p: {"n": 10, "median": m, "mean": m, "p95": p, "ci95_halfwidth": 0.1, "instantiation": "x"}
    a = {"p": {"lat": stats(1.0, 4.0), "tp": 10.0, "lb": False, "status": "ok"}}
    b = {"p": {"lat": stats(3.0, 6.0), "tp": 20.0, "lb": True, "status": "ok"}}
    out = agg.combine([a, b])["p"]
    assert out["lat"]["median"] == 2.0 and out["lat"]["p95"] == 5.0 and out["lat"]["reps"] == 2
    assert out["lat"]["ci95_halfwidth"] > 0 and out["lat"]["instantiation"] == "x"
    assert out["tp"] == 15.0 and out["tp_ci95"] > 0 and out["lb"] is True and out["status"] == "ok"


def test_remote_provers_never_dispatch_after_close():
    """A proof arriving after close() (end of an Exp. 1 point) must not send on the closed connection: the reader
    thread crashed with EBADF in repetition 1 (2026-10-17)."""
    import collections
    import threading

    from veredact_bench.evaluation.provers import RemoteProvers

    class Closed:
        def send(self, msg):
            raise OSError(9, "Bad file descriptor")

    rp = RemoteProvers.__new__(RemoteProvers)
    rp._conns, rp._load, rp._cap, rp._lock = [(Closed(), threading.Lock())], [0], [4], threading.Lock()
    rp._cb, rp._ids, rp._pending, rp._closed = {}, iter(range(10)), collections.deque(), False
    rp._pending.append((lambda: "job", lambda p, s: None))
    rp._pump()  # the send fails (closed under it): no exception escapes
    rp._closed = True
    rp._pending.append((lambda: "job", lambda p, s: None))
    rp._pump()  # closed: nothing is dispatched
    assert len(rp._pending) == 1


def test_exp4_reuses_the_exp3_history(tmp_path, monkeypatch):
    """Exp. 3 hands its history to Exp. 4 (same dataset and largest n_Q): one build, not two."""
    from veredact_bench.evaluation.experiments import exp03_audit_efficiency as exp03

    built = []
    real = exp03.open_system
    monkeypatch.setattr(exp03, "open_system", lambda *a, **k: built.append(a[1]) or real(*a, **k))
    c3, c4 = _cfg(tmp_path, "exp03_audit_efficiency"), _cfg(tmp_path, "exp04_verification_time")
    for c in (c3, c4):
        c["experiment"]["systems"], c["experiment"]["n_Q"], c["experiment"]["samples_per_point"] = ["S1"], [10], 1
    monkeypatch.setattr(exp03, "KEEP", True)
    RUNNERS["exp03_audit_efficiency"](c3, RunWriter(c3))
    assert len(exp03.SHARED) == 1
    RUNNERS["exp04_verification_time"](c4, RunWriter(c4))
    assert built == ["S1"] and not exp03.SHARED
    m = json.loads((tmp_path / "exp04_verification_time" / "S1" / "smoke" / "metrics.json").read_text())
    assert all(p["status"] == "ok" and p["false_rejection_rate"] == 0 for p in m["points"].values())


def test_exp3_history_not_kept_when_exp4_does_not_follow(tmp_path):
    from veredact_bench.evaluation.experiments import exp03_audit_efficiency as exp03

    c = _cfg(tmp_path, "exp03_audit_efficiency")
    c["experiment"]["systems"], c["experiment"]["n_Q"], c["experiment"]["samples_per_point"] = ["S1"], [10], 1
    assert exp03.KEEP is False
    RUNNERS["exp03_audit_efficiency"](c, RunWriter(c))
    assert not exp03.SHARED


def test_prover_service_starts_every_worker_before_ready(monkeypatch):
    """The first proofs of an Exp. 1 point came back 13-15 s after its start (lazily started prover workers):
    the service must answer ready only once every worker process runs."""
    import importlib
    import pathlib

    monkeypatch.syspath_prepend(str(pathlib.Path(__file__).parents[1] / "scripts"))
    ps = importlib.import_module("prover_service")  # importable by name: worker processes unpickle _warm
    pools = []

    class Pool(ps.ProcessPoolExecutor):
        def __init__(self, *a, **k):
            super().__init__(*a, **{**k, "initializer": None, "initargs": ()})
            pools.append(self)

    monkeypatch.setattr(ps, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(ps, "_check", lambda b: True)
    alive = []

    class Conn:
        msgs = [("init", {}), ("close",)]

        def recv(self):
            return self.msgs.pop(0)

        def send(self, m):
            alive.append((m, len(pools[0]._processes)))

        def close(self):
            pass

    ps.serve(Conn(), 3)
    assert alive == [(("ready", 3), 3)]


def test_remote_provers_report_a_host_lost_mid_point():
    """A spot prover reclaimed during a point drops its connection: RemoteProvers must report it (the point then
    fails instead of counting its requests as unfinished), but not after close()."""
    import threading

    from veredact_bench.evaluation.provers import RemoteProvers

    class Conn:
        def __init__(self):
            self.gone = threading.Event()

        def recv(self):
            self.gone.wait()
            raise EOFError

        def send(self, m):
            pass

        def close(self):
            self.gone.set()

    rp = RemoteProvers.__new__(RemoteProvers)
    rp._lock, rp._closed, rp.lost = threading.Lock(), False, []
    a, b = Conn(), Conn()
    rp._conns = [(a, threading.Lock()), (b, threading.Lock())]
    t = threading.Thread(target=rp._read, args=(0,))
    t.start()
    a.gone.set()  # host 0 vanishes mid-point
    t.join(5)
    assert rp.lost == [0]
    rp._closed = True  # after close(): a dropped connection is the normal end
    t = threading.Thread(target=rp._read, args=(1,))
    t.start()
    b.gone.set()
    t.join(5)
    assert rp.lost == [0]
