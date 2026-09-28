"""Statistics as reported in the paper: mean with 95% CI (Student t), median, p95, p99; CSV output."""
import csv
import math
import os
import statistics

# two-sided 95% Student-t critical values, df = 1..30; normal beyond
_T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
        2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048,
        2.045, 2.042]


def ci95(xs):
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else float("nan")), 0.0
    m, sd = statistics.fmean(xs), statistics.stdev(xs)
    t = _T95[n - 2] if n - 1 <= 30 else 1.96
    return m, t * sd / math.sqrt(n)


def percentile(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(xs, prefix=""):
    m, h = ci95(xs)
    return {f"{prefix}mean": m, f"{prefix}ci95": h, f"{prefix}median": percentile(xs, 0.5),
            f"{prefix}p95": percentile(xs, 0.95), f"{prefix}p99": percentile(xs, 0.99), f"{prefix}n": len(xs)}


class CsvWriter:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path, self.rows = path, []

    def add(self, **row):
        self.rows.append(row)
        print("  " + ", ".join(f"{k}={_fmt(v)}" for k, v in row.items()), flush=True)

    def save(self):
        keys = []
        for r in self.rows:
            keys += [k for k in r if k not in keys]
        with open(self.path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        print(f"-> {self.path} ({len(self.rows)} rows)")


def _fmt(v):
    return f"{v:.3f}" if isinstance(v, float) else str(v)
