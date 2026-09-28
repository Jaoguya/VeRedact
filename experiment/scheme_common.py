"""Shared helpers for the per-scheme experiment folders (experiment/S*/).

Each scheme folder holds a faithful, original-instantiation implementation of that paper
(s<ref>_scheme.py), its adapter to the shared Scheme contract used by Exp. 1-5 (s<ref>_baseline.py,
registered in benchmark/veredact_bench/registry.py), a runner that reproduces the paper's own
evaluation (s<ref>_run.py) and tests (s<ref>_test.py). Parameters come from config/schemes.toml [schemes.S<ref>.reproduction];
CSV output goes to results/S<ref>_<what>.csv.

Run from the repository root with the benchmark venv, e.g.
    benchmark/.venv/bin/python experiment/S1_ImprovedDCH/s1_run.py [--quick]
"""
import argparse
import csv
import statistics
import sys
import time
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"


def scheme_config(scheme_id: str, quick: bool = False) -> dict:
    """[schemes.S<ref>.reproduction] (+ its .quick overrides). No defaults in code: a missing key is a KeyError."""
    with open(REPO_ROOT / "config" / "schemes.toml", "rb") as f:
        r = dict(tomllib.load(f)["schemes"][scheme_id]["reproduction"])
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
        RESULTS.mkdir(exist_ok=True)
        self.path, self.rows = RESULTS / f"{name}.csv", []

    def add(self, **row):
        self.rows.append(row)
        print("  " + ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()),
              flush=True)

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


def add_folder_to_path(file: str):
    """Let s<ref>_run.py / s<ref>_test.py import their sibling s<ref>_scheme.py."""
    here = str(Path(file).resolve().parent)
    for p in (here, str(REPO_ROOT / "experiment")):
        if p not in sys.path:
            sys.path.insert(0, p)
