"""Combine independent repetitions of a tier: results/<exp>/<method>/<tier>-repNN/metrics.json (R of them)
-> results/<exp>/<method>/<tier>-reps/metrics.json with the same keys, each numeric value the MEAN over the
repetitions and its 95% confidence half-width (Student's t over the R per-repetition values) beside it:
  stats dicts ({"median", "p95", ...}): median = mean of the repetitions' medians, ci95_halfwidth = their CI
      (replaces the within-run CI); p95 = POOLED over every repetition's samples (hybrid plan 2026-10-31: 10 per
      run are too few for a p95), p95_ci95 = CI of the per-run p95s
  other numbers: mean, plus "<key>_ci95"; booleans (lower-bound flags): True if any repetition is True
A point missing from a repetition is an error (no silently shorter average). rows.csv of small experiments
(exp00, exp05) is concatenated for the tables. Experiments in config.ONCE (run 1 only) are copied from rep01 as
they are (their within-run CIs: Exp. 1 sub-windows and bootstrap).
Usage: scripts/aggregate_reps.py --tier experiment --reps 3
"""

import argparse
import csv
import json
import shutil

from veredact_bench import metrics as M
from veredact_bench.evaluation.summaries import summarize
from veredact_bench.utils.config import ONCE, REPO_ROOT, experiments, load

R = REPO_ROOT / "results"
CONCAT_ROWS = ("exp00_primitives", "exp05_blockchain_overhead")


def _ci(xs):
    return M.ci95_halfwidth(xs) if len(xs) > 1 else 0.0


def combine(vals: list, pooled=None):
    """vals: the same metrics node from every repetition; pooled: that node summarized over all their rows."""
    v0 = vals[0]
    if isinstance(v0, dict):
        if set(v0) >= {"median", "p95"} and all(v.get("n") for v in vals):  # a stats dict
            med, p95 = [v["median"] for v in vals], [v["p95"] for v in vals]
            pool = pooled if isinstance(pooled, dict) and pooled.get("n") else None
            return {
                "n": sum(v["n"] for v in vals),
                "median": M.mean(med),
                "mean": M.mean([v["mean"] for v in vals]),
                "p95": pool["p95"] if pool else M.mean(p95),
                "p95_pooled": bool(pool),
                "ci95_halfwidth": _ci(med),
                "p95_ci95": _ci(p95),
                "reps": len(vals),
                **{k: x for k, x in v0.items() if isinstance(x, str)},  # e.g. a primitive's instantiation
            }
        keys = set().union(*(v.keys() for v in vals))
        out = {}
        for k in sorted(keys):
            sub = [v.get(k) for v in vals]
            out[k] = combine(sub, pooled.get(k) if isinstance(pooled, dict) else None)
            if isinstance(v0.get(k), (int, float)) and not isinstance(v0.get(k), bool) and None not in sub:
                out[f"{k}_ci95"] = _ci(sub)
        return out
    if isinstance(v0, bool):
        return any(bool(v) for v in vals)
    if isinstance(v0, (int, float)):
        xs = [v for v in vals if v is not None]
        return M.mean(xs) if len(xs) == len(vals) else None
    return v0  # text (status, instantiation)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="experiment")
    ap.add_argument("--reps", type=int, required=True)
    a = ap.parse_args()
    folders = [f"{a.tier}-rep{r:02d}" for r in range(1, a.reps + 1)]
    for exp in experiments():
        reps = 1 if exp in ONCE else a.reps
        systems = set(load(a.tier, exp)["experiment"]["systems"])
        for mdir in sorted(p for p in (R / exp).iterdir() if p.is_dir()) if (R / exp).exists() else []:
            if mdir.name not in systems:  # an earlier run's system this experiment no longer runs: never mixed in
                print(f"{mdir.relative_to(R)}: not in {exp}'s systems, skipped")
                continue
            have = [mdir / f for f in folders[:reps] if (mdir / f / "metrics.json").exists()]
            if not have:
                continue
            if len(have) != reps:
                raise SystemExit(f"{mdir.relative_to(R)}: {len(have)} of {reps} repetitions finished")
            ms = [json.loads((d / "metrics.json").read_text()) for d in have]
            missing = [str(d.name) for d, m in zip(have, ms) if set(m["points"]) != set(ms[0]["points"])]
            if missing:
                raise SystemExit(f"{mdir.relative_to(R)}: points differ between repetitions ({missing})")
            out = mdir / f"{a.tier}-reps"
            if out.exists():
                shutil.rmtree(out)
            out.mkdir()
            if reps == 1:  # run once: its own metrics, unchanged
                m = ms[0] | {"reps": 1, "ci": "within the one run (Exp. 1: sub-windows, bootstrap p95)"}
                (out / "metrics.json").write_text(json.dumps(m, indent=2))  # reps: figures draw its error bars
                if exp in CONCAT_ROWS:
                    shutil.copy(have[0] / "rows.csv", out / "rows.csv")
                (out / "run_info.json").write_text(json.dumps({"aggregated_from": [have[0].name]}, indent=2))
                print(f"{out.relative_to(R)}: run once (copied)")
                continue
            rows = []
            for d in have:
                with open(d / "rows.csv", newline="") as f:
                    rows += list(csv.DictReader(f))
            pooled = summarize(exp, rows, load(a.tier, exp))["points"]
            agg = {"experiment": exp, "reps": reps, "rows": sum(m["rows"] for m in ms)}
            agg["points"] = combine([m["points"] for m in ms], pooled)
            (out / "metrics.json").write_text(json.dumps(agg, indent=2))
            (out / "run_info.json").write_text(json.dumps({"aggregated_from": [d.name for d in have]}, indent=2))
            if exp in CONCAT_ROWS:
                with open(out / "rows.csv", "w") as w:
                    for i, d in enumerate(have):
                        lines = (d / "rows.csv").read_text().splitlines(keepends=True)
                        w.writelines(lines if i == 0 else lines[1:])
            print(f"{out.relative_to(R)}: {reps} repetitions")


if __name__ == "__main__":
    main()
