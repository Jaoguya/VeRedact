"""Shared helpers for reproducing each baseline paper's OWN evaluation (methods/baselines/<scheme>/reproduce.py).

Each baseline folder holds a faithful, original-instantiation implementation of that paper (construction.py),
its adapter to the shared Scheme interface used by the experiments (adapter.py, registered in
methods/registry.py) and the reproduction of the paper's own figures (reproduce.py); its tests live in
tests/baselines/. Parameters come from configs/methods/<scheme>.yaml (reproduction section); CSV output goes
to results/reproduction/<scheme>/<what>.csv.

Run from the repository root:  python scripts/paper_reproduction.py <scheme> [--quick]
"""

import argparse
import csv
import statistics
import time

from veredact_bench.utils.config import REPO_ROOT, load

RESULTS = REPO_ROOT / "results" / "reproduction"


def scheme_config(scheme_id: str, quick: bool = False) -> dict:
    """configs/methods/<scheme>.yaml schemes.<id>.reproduction (+ its quick overrides). No defaults in code."""
    r = dict(load("experiment")["schemes"][scheme_id]["reproduction"])
    q = r.pop("quick")
    return {**r, **q} if quick else r


def median_ms(fn, reps: int) -> float:
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t) * 1000)
    return statistics.median(ts)


class Csv:
    def __init__(self, name: str):
        scheme, what = name.split("_", 1)  # "S13_audit" -> results/reproduction/S13/audit.csv
        (RESULTS / scheme).mkdir(parents=True, exist_ok=True)
        self.path, self.rows = RESULTS / scheme / f"{what}.csv", []

    def add(self, **row):
        self.rows.append(row)
        print(
            "  " + ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()), flush=True
        )

    def save(self):
        keys = list(dict.fromkeys(k for r in self.rows for k in r))
        with open(self.path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        print(f"-> {self.path.relative_to(REPO_ROOT)} ({len(self.rows)} rows)")


def cli(description: str):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--quick", action="store_true", help="fewer repetitions and a trimmed sweep")
    return ap.parse_args()
