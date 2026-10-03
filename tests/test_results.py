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
    assert w.begin("veredact:per_request")
    w.row(system="veredact:per_request", symbol="T_H", instantiation="x", sample=0, ms=1.0)
    w.end()
    d = tmp_path / "exp00_primitives" / "veredact-per_request" / "smoke"
    assert {p.name for p in d.iterdir()} == FILES
    assert json.loads((d / "metrics.json").read_text())["rows"] == 1
    assert not RunWriter(cfg).begin("veredact:per_request")          # done: skipped
    w2 = RunWriter(cfg, force=True)
    assert w2.begin("veredact:per_request")                          # forced: folder replaced
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
