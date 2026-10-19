"""Combine independent repetitions of a tier: results/<exp>/<method>/<tier>-repNN/metrics.json (R of them)
-> results/<exp>/<method>/<tier>-reps/metrics.json with the same keys, each numeric value the MEAN over the
repetitions and its 95% confidence half-width (Student's t over the R per-repetition values) beside it:
  stats dicts ({"median", "p95", ...}): median and p95 = means of the repetitions' medians / p95s,
      ci95_halfwidth = CI of the repetitions' medians (replaces the within-run CI), p95_ci95 = CI of the p95s
  other numbers: mean, plus "<key>_ci95"; booleans (lower-bound flags): True if any repetition is True
A point missing from a repetition is an error (no silently shorter average). rows.csv of small experiments
(exp00, exp05) is concatenated for the tables. Usage: scripts/aggregate_reps.py --tier experiment --reps 10
"""

import argparse
import json
import shutil

from veredact_bench import metrics as M
from veredact_bench.utils.config import REPO_ROOT, experiments

R = REPO_ROOT / "results"
CONCAT_ROWS = ("exp00_primitives", "exp05_gas_consumption")


def _ci(xs):
    return M.ci95_halfwidth(xs) if len(xs) > 1 else 0.0


def combine(vals: list):
    """vals: the same metrics node from every repetition."""
    v0 = vals[0]
    if isinstance(v0, dict):
        if set(v0) >= {"median", "p95"} and all(v.get("n") for v in vals):  # a stats dict
            med, p95 = [v["median"] for v in vals], [v["p95"] for v in vals]
            return {
                "n": sum(v["n"] for v in vals),
                "median": M.mean(med),
                "mean": M.mean([v["mean"] for v in vals]),
                "p95": M.mean(p95),
                "ci95_halfwidth": _ci(med),
                "p95_ci95": _ci(p95),
                "reps": len(vals),
                **{k: x for k, x in v0.items() if isinstance(x, str)},  # e.g. a primitive's instantiation
            }
        keys = set().union(*(v.keys() for v in vals))
        out = {}
        for k in sorted(keys):
            sub = [v.get(k) for v in vals]
            out[k] = combine(sub)
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
        for mdir in sorted(p for p in (R / exp).iterdir() if p.is_dir()) if (R / exp).exists() else []:
            have = [mdir / f for f in folders if (mdir / f / "metrics.json").exists()]
            if not have:
                continue
            if len(have) != a.reps:
                raise SystemExit(f"{mdir.relative_to(R)}: {len(have)} of {a.reps} repetitions finished")
            ms = [json.loads((d / "metrics.json").read_text()) for d in have]
            missing = [str(d.name) for d, m in zip(have, ms) if set(m["points"]) != set(ms[0]["points"])]
            if missing:
                raise SystemExit(f"{mdir.relative_to(R)}: points differ between repetitions ({missing})")
            out = mdir / f"{a.tier}-reps"
            if out.exists():
                shutil.rmtree(out)
            out.mkdir()
            agg = {"experiment": exp, "reps": a.reps, "rows": sum(m["rows"] for m in ms)}
            agg["points"] = combine([m["points"] for m in ms])
            (out / "metrics.json").write_text(json.dumps(agg, indent=2))
            (out / "run_info.json").write_text(json.dumps({"aggregated_from": [d.name for d in have]}, indent=2))
            if exp in CONCAT_ROWS:
                with open(out / "rows.csv", "w") as w:
                    for i, d in enumerate(have):
                        lines = (d / "rows.csv").read_text().splitlines(keepends=True)
                        w.writelines(lines if i == 0 else lines[1:])
            print(f"{out.relative_to(R)}: {a.reps} repetitions")


if __name__ == "__main__":
    main()
