"""Read results/<experiment>/<method>/<tier>/ for reporting (rows, metrics, run info), and list what exists."""
import csv
import json

from veredact_bench.utils.config import REPO_ROOT

RESULTS = REPO_ROOT / "results"


def runs(experiment: str, tier: str) -> dict:
    """method key -> run folder, for every finished (metrics.json present) method of the experiment."""
    out = {}
    for d in sorted((RESULTS / experiment).glob(f"*/{tier}")):
        if (d / "metrics.json").exists():
            out[d.parent.name.replace("-", ":", 1)] = d
    return out


def rows(experiment: str, tier: str) -> list[dict]:
    out = []
    for d in runs(experiment, tier).values():
        with open(d / "rows.csv") as f:
            out += list(csv.DictReader(f))
    return out


def metrics(experiment: str, tier: str) -> dict:
    return {k: json.loads((d / "metrics.json").read_text()) for k, d in runs(experiment, tier).items()}


def run_info(experiment: str, tier: str) -> dict:
    return {k: json.loads((d / "run_info.json").read_text()) for k, d in runs(experiment, tier).items()}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
