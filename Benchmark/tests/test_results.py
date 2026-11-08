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

    # S98: a method the paper does not compare; the VeRedact-PQ ablation variants are paper systems
    # (VeRedact-optimize.tex Exp. 1-3, 2026-10-24) and are drawn in the paper's order
    keys = ["S98", "veredact-cora-no-sfmr", "veredact", "S1", "S13", "S27", "S34", "S99"]
    monkeypatch.setattr(figures, "_all_metrics", lambda exp, tier: {k: {"points": {}} for k in keys})
    drawn = list(figures.metrics("exp01_redaction_throughput", "smoke"))
    assert drawn == ["veredact", "veredact-cora-no-sfmr", "S1", "S13", "S27", "S34", "S99"]
    assert set(style.VARIANTS) <= set(style.PAPER_METHODS)
    assert tables.ORDER == list(style.PAPER_METHODS)  # a table lists only the systems its experiment ran


def test_blockchain_overhead_figure(monkeypatch, tmp_path):
    """#9 redesign: Fig. 7 is one panel, PBN anchoring transactions per finalized redaction vs arrival rate, one
    line per system, read from Exp. 1's points (the same workload; each point counts its own anchoring)."""
    from veredact_bench.reporting import figures, style

    def fake(exp, tier):
        assert exp == "exp01_redaction_throughput"
        per = {"veredact": 0.02, "S1": 1.0, "S27": 1.0}
        return {
            k: {
                "points": {
                    f"sweep=rate|rate_rps={r}|zipf_s=0.8": {"anchor_tx_per_finalized": v, "finalized_all": 9}
                    for r in (25, 100)
                }
            }
            for k, v in per.items()
        }

    monkeypatch.setattr(figures, "_all_metrics", fake)
    monkeypatch.setattr(figures, "OUT", tmp_path)
    monkeypatch.setattr(figures, "load", lambda tier, exp: {"experiment": {"rates": [25, 100]}})
    drawn = {}
    save = lambda fig, name, w: drawn.update({name: [[list(ln.get_ydata()) for ln in a.lines] for a in fig.axes]})
    monkeypatch.setattr(figures, "_save", save)
    style.apply()
    figures.fig_exp5("smoke", [])
    (lines,) = drawn["exp5_blockchain_overhead"]
    assert sorted(lines) == [[0.02, 0.02], [1.0, 1.0], [1.0, 1.0]]


def test_anchor_logs_every_submitted_transaction_size():
    """#9: every anchor keeps (op, size) of each submitted transaction, so Exp. 1 can count a point's PBN load."""
    from veredact_bench.evaluation.anchor import InProcessAnchor

    a = InProcessAnchor()
    a.submit("baseline_redaction", commit=b"x" * 32)
    a.submit("rai_checkpoint", epoch=1, cp=b"y" * 32)
    assert a.txlog == [("baseline_redaction", 32), ("rai_checkpoint", 64)]


def test_exp1_point_records_its_anchoring_load(tmp_path):
    """#9: each Exp. 1 point records the anchoring transactions (count, bytes, gas) submitted after setup; a
    baseline writes one ledger transaction per executed redaction."""
    import csv

    from veredact_bench.evaluation.experiments.exp01_redaction_throughput import run_point

    cfg = _cfg(tmp_path, "exp01_redaction_throughput")
    cfg["experiment"].update(warmup_s=0, duration_s=1, drain_s=2, requester_cores=0, fault_fraction=0.0)
    out = RunWriter(cfg)
    assert out.begin("S27")
    run_point(cfg, "S27", 20, 0.8, out, "rate")
    out.end()
    with open(tmp_path / "exp01_redaction_throughput" / "S27" / "smoke" / "rows.csv") as f:
        rows = list(csv.DictReader(f))
    finalized = sum(r["status"] == "finalized" for r in rows)
    assert finalized and {r["anchor_tx"] for r in rows} == {str(finalized)}
    assert int(rows[0]["anchor_tx_bytes"]) > 0


def test_exp1_anchoring_load_per_finalized_redaction():
    """#9: metrics.json divides a point's anchoring transactions, bytes and gas by its finalized redactions (any
    request the scheme executed, valid or not: each one occupied the ledger)."""
    from veredact_bench.evaluation.summaries import _exp01

    def row(seq, fault, status):
        return dict(
            sweep="rate",
            rate_rps=100,
            zipf_s=0.8,
            seq=seq,
            in_window=1,
            fault=fault,
            status=status,
            batch_id=1,
            batch_adaptations=1,
            submit_s=20.0,
            latency_ms=1_000 if status == "finalized" else "",
            arrival_s=20.0,
            anchor_tx=2,
            anchor_tx_bytes=8000,
            anchor_gas=600,
        )

    rows = [row(1, "", "finalized"), row(2, "", "finalized"), row(3, "stale", "finalized"), row(4, "", "rejected")]
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    assert pt["finalized_all"] == 3
    assert abs(pt["anchor_tx_per_finalized"] - 2 / 3) < 1e-9
    assert abs(pt["anchor_bytes_per_finalized"] - 8000 / 3) < 1e-9 and abs(pt["anchor_gas_per_finalized"] - 200) < 1e-9


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


def test_exp1_counts_accepted_invalid_requests_never_as_throughput():
    """#5 redesign: throughput counts valid finalized redactions only; an invalid request (stale or absent) that a
    scheme executes is an accepted invalid request, reported per point."""
    from veredact_bench.evaluation.summaries import _exp01

    def row(seq, fault, status):
        return dict(
            sweep="rate",
            rate_rps=100,
            zipf_s=0.8,
            seq=seq,
            in_window=1,
            fault=fault,
            status=status,
            batch_id=seq,
            batch_adaptations=1,
            submit_s=20.0,
            latency_ms=1_000 if status == "finalized" else "",
            arrival_s=20.0,
        )

    rows = [row(1, "", "finalized"), row(2, "stale", "finalized"), row(3, "absent", "rejected")]
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    assert pt["completed_in_window"] == 1 and abs(pt["throughput_per_s"] - 1 / 60) < 1e-9
    assert pt["invalid_offered"] == 2 and pt["invalid_accepted"] == 1 and pt["invalid_accepted_rate"] == 0.5


def test_exp1_figure_is_one_panel_of_valid_throughput(monkeypatch):
    """#5 redesign: Fig. 3 is one panel (finalized valid redactions/s vs offered load), one line per system."""
    from veredact_bench.reporting import figures, style

    def pt(tp):
        return {"completed_in_window": 10, "throughput_per_s": tp, "latency_ms": {"n": 1, "p95": 1.0}}

    pts = {f"sweep=rate|rate_rps={r}|zipf_s=0.8": pt(r / 2) for r in (25, 100)}
    fake = {k: {"points": pts} for k in ("veredact", "S27")}
    monkeypatch.setattr(figures, "_all_metrics", lambda exp, tier: fake)
    monkeypatch.setattr(figures, "load", lambda tier, exp: {"experiment": {"rates": [25, 100]}})
    drawn = {}
    monkeypatch.setattr(figures, "_save", lambda fig, name, w: drawn.update({name: [len(a.lines) for a in fig.axes]}))
    style.apply()
    figures.fig_exp1("smoke", [])
    assert drawn["exp1_redaction_throughput"] == [2]


def test_exp1_single_run_cis_from_subwindows_and_bootstrap():
    """Exp. 1 runs once: throughput CI over 6 sub-windows (steady 1/s -> 0), p95 CI by bootstrap (> 0, seeded)."""
    from veredact_bench import metrics as M
    from veredact_bench.evaluation.summaries import _exp01

    rows = [
        dict(
            sweep="rate",
            rate_rps=1,
            zipf_s=0.8,
            seq=i,
            in_window=1,
            fault="",
            status="finalized",
            batch_id=i,
            batch_adaptations=1,
            arrival_s=10.0 + i,
            submit_s=10.0 + i,
            latency_ms=100 + i,
            cutoff_s=100.0,
        )
        for i in range(60)
    ]  # one finalized per second over the 60 s window
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    assert pt["throughput_per_s"] == 1.0 and pt["throughput_per_s_ci95"] == 0.0
    assert pt["latency_ms"]["p95_ci95"] > 0
    xs = list(range(1000))
    assert M.bootstrap_ci95_halfwidth(xs, 95) == M.bootstrap_ci95_halfwidth(xs, 95)


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


def test_exp3_end_to_end_is_generation_plus_verification_per_query():
    """#7 redesign: the end-to-end audit cost of a query is its response generation plus its verification, summed
    per query (one row) before the statistics, never median + median."""
    from veredact_bench.evaluation.summaries import _exp03

    def row(gen, ver):
        return dict(records_per_batch=64, n_Q=10, status="ok", retrieval_ms=gen, verify_ms=ver, evidence_bytes=1)

    (pt,) = _exp03([row(1.0, 100.0), row(50.0, 2.0), row(3.0, 3.0)], {}).values()
    assert pt["end_to_end_ms"]["median"] == 52.0  # per-query sums 101, 52, 6 (median + median would be 3 + 3)


def test_exp3_figure_is_one_panel_of_end_to_end_cost(monkeypatch):
    """#7 redesign: Fig. 5 is one panel, end-to-end audit cost per query vs n_Q at the default sharing level."""
    from veredact_bench.reporting import figures, style

    def pt(y):
        return {"status": "ok", "end_to_end_ms": {"n": 3, "median": y}}

    pts = {f"records_per_batch={r}|n_Q={n}": pt(r * n) for r in (1, 64) for n in (10, 100)}
    fake = {k: {"points": pts} for k in ("veredact", "veredact-shared-evidence", "S13")}
    monkeypatch.setattr(figures, "_all_metrics", lambda exp, tier: fake)
    monkeypatch.setattr(figures, "load", lambda tier, exp: {"veredact": {"reference_batch": 64}})
    drawn = {}
    save = lambda fig, name, w: drawn.update({name: [[list(ln.get_ydata()) for ln in a.lines] for a in fig.axes]})
    monkeypatch.setattr(figures, "_save", save)
    style.apply()
    figures.fig_exp3("smoke", [])
    (lines,) = drawn["exp3_audit_efficiency"]
    assert lines == [[640, 6400]] * 3  # every system at records_per_batch = 64


def test_exp4_detection_rate_undefined_when_nothing_injected():
    from veredact_bench.evaluation.summaries import _exp04

    rows = [
        dict(
            n_Q=10,
            deep_fraction=0.0,
            fault_kind="modified",
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
    assert v["auth_with_net_per_request_ms"] == {"n": 0}  # rows without the network column: no Fig. 4 value


def test_exp2_figure_value_adds_the_committee_network_time():
    """Fig. 4 line = complete authorization per request + its committee message delay (fairness fix, option 1);
    VeRedact-PQ pays one round per set of m, Scheme [1] one per request."""
    from veredact_bench.evaluation.summaries import _exp02

    rows = [
        dict(
            committee_n=4,
            batch_size=2,
            sample=0,
            phase3_ms=p3,
            phase4_batch_ms=4.0,
            auth_ok=1,
            auth_per_request_ms=1.0,
            batch_total_ms=1.0,
            auth_net_per_request_ms=5.0,  # one 10 ms round shared by m = 2
        )
        for p3 in (1.0, 3.0)
    ]
    (v,) = _exp02(rows, {}).values()
    assert v["auth_complete_per_request_ms"]["median"] == 4.0  # crypto, for the text
    assert v["auth_with_net_per_request_ms"]["median"] == 9.0  # the plotted value


def test_exp2_figure_is_one_panel_of_complete_cost_vs_committee_size(monkeypatch):
    """#6 redesign: Fig. 4 is one panel, complete authorization per request (Phase 3 + Phase 4 / m) vs committee
    size n at the reference round m; a scheme without a batch protocol is drawn dashed."""
    from veredact_bench.reporting import figures, style

    def pt(y, batched):
        return {
            "auth_with_net_per_request_ms": {"n": 3, "median": y},
            "phase4_batch_ms": {"n": 3 if batched else 0},
        }

    def fake(exp, tier):
        out = {}
        for key, batched in (("veredact", True), ("S1", False), ("S99", True)):
            out[key] = {
                "points": {f"committee_n={n}|batch_size={m}": pt(n + m, batched) for n in (4, 7, 64) for m in (1, 64)}
            }
        return out

    monkeypatch.setattr(figures, "_all_metrics", fake)
    monkeypatch.setattr(figures, "load", lambda tier, exp: {"veredact": {"committee_n": 7, "reference_batch": 64}})
    drawn = {}

    def save(fig, name, w):
        drawn[name] = [
            [(ln.get_linestyle(), list(ln.get_xdata()), list(ln.get_ydata())) for ln in a.lines] for a in fig.axes
        ]

    monkeypatch.setattr(figures, "_save", save)
    style.apply()
    figures.fig_exp2("smoke", [])
    (lines,) = drawn["exp2_authorization_latency"]
    assert len(lines) == 3
    assert all(xs == [4, 7, 64] for _, xs, _ in lines)
    assert sorted(ys[0] for _, _, ys in lines) == [68, 68, 68]  # m = 64 at n = 4
    assert sorted(ls for ls, _, _ in lines) == ["-", "-", "--"]  # S1 has no batch protocol: dashed


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


def test_exp1_clients_share_one_deadline():
    """S13 at 5,000 req/s (2026-10-21) stopped after 386 s: each client thread was joined with its own drain-long
    timeout. join_by gives all of them ONE deadline, however many are still busy."""
    import threading
    import time

    from veredact_bench.evaluation.experiments.exp01_redaction_throughput import join_by

    busy = [threading.Thread(target=time.sleep, args=(3.0,), daemon=True) for _ in range(4)]
    for th in busy:
        th.start()
    t = time.perf_counter()
    join_by(busy, t + 0.5)
    assert time.perf_counter() - t < 1.5  # per-thread timeouts would wait 4 x 0.5 = 2 s


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
                return {"status": 1, "gasUsed": 21000, "blockNumber": 7}
            raise ValueError("not found")

        def get_transaction(self, h):
            raise ValueError("not found")

        def send_raw_transaction(self, raw):
            self.sent.append(raw)

    a = object.__new__(BesuAnchor)
    a.w3 = type("W3", (), {"eth": Eth()})()
    a._plock, a.recheck_s, a.timeout_s = threading.Lock(), 30.0, 600.0
    a.recovered = {"late_receipt": 0, "resent": 0, "timed_out": 0}
    a._cp_keys, a.cp_block = {}, {}
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


def test_repetition_splits_samples_except_once_experiments(monkeypatch):
    """Hybrid plan: a repeated experiment takes ceil(n / 3) samples per run (30 -> 10, S13 5 -> 2); Exp. 0 keeps all."""
    from veredact_bench.utils.config import load

    monkeypatch.setenv("VRPQ_REP", "2")
    e3 = load("experiment", "exp03_audit_efficiency")["experiment"]
    assert e3["samples_per_point"] == 10 and e3["samples_override"]["S13"]["10000"] == 2
    assert load("experiment", "exp00_primitives")["experiment"]["samples_per_point"] == 100


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


def test_three_run_aggregate_ci_is_students_t_with_two_degrees_of_freedom():
    import importlib.util

    import pytest

    from veredact_bench.utils.config import REPO_ROOT

    spec = importlib.util.spec_from_file_location("agg", REPO_ROOT / "scripts" / "aggregate_reps.py")
    agg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agg)
    st = lambda m: {"n": 30, "median": m, "mean": m, "p95": m, "ci95_halfwidth": 0.0}
    out = agg.combine([{"p": st(1.0)}, {"p": st(2.0)}, {"p": st(3.0)}])["p"]
    # t(0.975, 2) = 4.302653, sample sd = 1, n = 3: 4.302653 / sqrt(3)
    assert out["median"] == 2.0 and out["reps"] == 3
    assert out["ci95_halfwidth"] == pytest.approx(2.48414, abs=1e-4)


def test_aggregate_p95_is_pooled_over_runs():
    """Hybrid plan: 10 samples per run are too few for a p95, so the aggregate p95 is the pooled one; the median and
    its CI stay over the per-run medians."""
    import importlib.util

    from veredact_bench.utils.config import REPO_ROOT

    spec = importlib.util.spec_from_file_location("agg", REPO_ROOT / "scripts" / "aggregate_reps.py")
    agg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agg)
    st = lambda m, p: {"n": 10, "median": m, "mean": m, "p95": p, "ci95_halfwidth": 0.0}
    pooled = {"p": {"lat": {"n": 30, "median": 2.0, "mean": 2.0, "p95": 9.0, "ci95_halfwidth": 0.0}}}
    out = agg.combine([{"p": {"lat": st(1.0, 4.0)}}, {"p": {"lat": st(3.0, 6.0)}}], pooled)["p"]["lat"]
    assert out["p95"] == 9.0 and out["p95_pooled"] and out["median"] == 2.0


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


def test_exp4_s13_per_block_runs_on_s13s_history(tmp_path):
    """#8: S13-per-block audits S13's own history (same history_id) and decides per block: under every fault
    class it rejects all tampered records, and it keeps valid records of untouched blocks where S13's aggregate
    Audit keeps none."""
    c = _cfg(tmp_path, "exp04_verification_time")
    c["experiment"]["systems"], c["experiment"]["n_Q"], c["experiment"]["samples_per_point"] = (
        ["S13", "S13-per-block"],
        [100],
        1,
    )
    RUNNERS["exp04_verification_time"](c, RunWriter(c))
    m = {
        k: json.loads((tmp_path / "exp04_verification_time" / k / "smoke" / "metrics.json").read_text())
        for k in c["experiment"]["systems"]
    }
    hid = {k: {p["history_id"] for p in m[k]["points"].values()} for k in m}
    assert hid["S13"] == hid["S13-per-block"] and len(hid["S13"]) == 1
    faults = [k for k in m["S13-per-block"]["points"] if "fault_kind=none" not in k]
    assert faults
    for k in faults:
        per_block, whole = m["S13-per-block"]["points"][k], m["S13"]["points"][k]
        assert per_block["status"] == "ok" and per_block["detection_rate"] == 1.0
        assert per_block["valid_acceptance_rate"] >= whole["valid_acceptance_rate"]
    assert any(m["S13-per-block"]["points"][k]["valid_acceptance_rate"] > 0 for k in faults)


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


def test_prover_whose_proof_fails_here_is_refused():
    """Graviton provers, x86 system: a host's first proof must verify on the system, else the point never starts."""
    import pytest

    from veredact_bench.evaluation.provers import _cross_check

    class Conn:
        def send(self, m):
            self.job = m

        def recv(self):
            return ("done", -1, b"proof", b"sig")

    class Zk:
        def __init__(self, ok):
            self.ok = ok

        def verify(self, requester, x, proof, threshold, ts):
            return self.ok and proof == b"proof"

    _cross_check("h:1", Conn(), Zk(True))
    with pytest.raises(RuntimeError, match="does not verify"):
        _cross_check("h:1", Conn(), Zk(False))


def test_remote_provers_report_a_host_lost_mid_point():
    """A prover host lost during a point drops its connection: RemoteProvers must report it (the point then
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


def test_variant_result_folders_keep_their_system_key(tmp_path, monkeypatch):
    """results/<exp>/veredact-per-request/<tier> is read back as system key veredact-per-request (the figures look
    the variants up by that key)."""
    from veredact_bench.reporting import load as rload

    for key in ("veredact", "veredact-per-request"):
        d = tmp_path / "exp01_redaction_throughput" / key / "smoke"
        d.mkdir(parents=True)
        (d / "metrics.json").write_text("{}")
    monkeypatch.setattr(rload, "RESULTS", tmp_path)
    assert sorted(rload.runs("exp01_redaction_throughput", "smoke")) == ["veredact", "veredact-per-request"]


def test_coverage_of_one_part_checks_only_its_experiments(tmp_path, monkeypatch, capsys):
    """A split-run worker holds one part: its coverage check must not report the other parts' experiments as gaps."""
    import importlib.util
    import sys

    import pytest

    from veredact_bench.utils.config import REPO_ROOT

    spec = importlib.util.spec_from_file_location("cov", REPO_ROOT / "scripts" / "check_coverage.py")
    cov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cov)
    monkeypatch.setattr(cov, "R", tmp_path)  # no results at all: every checked point is a gap
    argv = ["check_coverage", "--tier", "smoke", "--experiments", "exp05_blockchain_overhead"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cov.main()
    gaps = [line for line in capsys.readouterr().out.splitlines() if line.startswith("GAP")]
    assert gaps and all("exp05_blockchain_overhead" in g for g in gaps)
