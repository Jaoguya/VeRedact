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


def test_paper_artifacts_show_only_the_five_schemes(monkeypatch):
    from veredact_bench.reporting import figures, style, tables

    keys = ["veredact", "S99", "S1", "S13", "S27", "S34"]  # S99: a method the paper does not compare
    monkeypatch.setattr(figures, "_all_metrics", lambda exp, tier: {k: {"points": {}} for k in keys})
    assert list(figures.metrics("exp01_redaction_throughput", "smoke")) == list(style.PAPER_METHODS)
    assert tables.ORDER == ["veredact", "S1", "S13", "S27", "S34"]


def test_gas_figure_draws_one_line_per_scheme(monkeypatch, tmp_path):
    from veredact_bench.reporting import figures, style

    def fake(exp, tier):  # two skews x two batch sizes per scheme, as Exp. 5 records them
        pts = {f"zipf_s={s}|batch_size={b}": {"gas_per_redaction": 1000.0 + b} for s in (0.0, 0.8) for b in (1, 8)}
        return {k: {"points": pts} for k in style.PAPER_METHODS}

    monkeypatch.setattr(figures, "_all_metrics", fake)
    monkeypatch.setattr(figures, "OUT", tmp_path)
    drawn = {}
    monkeypatch.setattr(figures, "_save", lambda fig, name, w: drawn.update({name: [len(a.lines) for a in fig.axes]}))
    style.apply()
    figures.fig_exp5("smoke", [])
    assert drawn["exp5_gas_consumption"] == [len(style.PAPER_METHODS)] * 2


def test_exp1_adaptations_count_every_finalized_redaction():
    """Fig. 3(c): a scheme that finalizes nothing inside the window still gets an adaptation count."""
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
        )

    rows = [row(1, 0, 5.0, 10_000), row(2, 1, 20.0, 1_000), row(3, 1, 25.0, 60_000)]  # done at 15 s, 21 s, 85 s
    (pt,) = _exp01(rows, {"experiment": {"duration_s": 60, "warmup_s": 10}}).values()
    assert pt["completed_in_window"] == 2 and pt["finalized"] == 2  # rows 1+2 vs arrival cohort rows 2+3
    assert abs(pt["throughput_per_s"] - 2 / 60) < 1e-9
