"""Metrics: pure functions (no I/O, no global state). Tables and figures compute every number through these.

One run per configuration point (configs/base.yaml): a point's statistics come from the samples inside
that run (every request in Exp. 1, every authorization batch / audit query in Exp. 2-4, every primitive
call in exp00). Confidence intervals of the mean use Student's t; comparisons between two systems use
the two-sided Mann-Whitney U test (unpaired: two systems never see the same request at the same time).
Both come from scipy.stats.
"""

import math
from collections.abc import Sequence

from scipy import stats


def _sorted(values: Sequence[float]) -> list[float]:
    xs = sorted(float(v) for v in values)
    if not xs:
        raise ValueError("no samples")
    return xs


def percentile(values: Sequence[float], q: float) -> float:
    """q-th percentile, linear interpolation between closest ranks (NumPy's default method)."""
    if not 0 <= q <= 100:
        raise ValueError("q must be in [0, 100]")
    xs = _sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def median(values: Sequence[float]) -> float:
    return percentile(values, 50)


def mean(values: Sequence[float]) -> float:
    xs = _sorted(values)
    return sum(xs) / len(xs)


def std(values: Sequence[float]) -> float:
    """Sample standard deviation (n - 1)."""
    xs = _sorted(values)
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ci95_halfwidth(values: Sequence[float]) -> float:
    """Half-width of the 95% CI of the mean: t_{0.975, n-1} * s / sqrt(n)."""
    xs = _sorted(values)
    n = len(xs)
    return float(stats.t.ppf(0.975, n - 1)) * std(xs) / math.sqrt(n) if n > 1 else 0.0


def throughput(completed: int, duration_s: float) -> float:
    """Completed operations per second over a measurement window."""
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    return completed / duration_s


def per_thousand(events: float, completed: int) -> float:
    """Events per 1,000 completed operations (e.g. PQCH adaptations per 1,000 finalized redactions)."""
    if completed <= 0:
        raise ValueError("no completed operations")
    return 1000.0 * events / completed


def rate(hits: int, total: int) -> float:
    """hits / total, e.g. detected tampered records / injected, falsely rejected / valid."""
    return hits / total if total else 0.0


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Two-sided Mann-Whitney U test (scipy.stats.mannwhitneyu, method "auto": exact for small samples
    without ties, normal approximation with tie and continuity correction otherwise).
    Returns (U of sample a, p-value); U counts pairs (x in a, y in b) with x > y, ties counting one half."""
    a, b = [float(v) for v in a], [float(v) for v in b]
    if not a or not b:
        raise ValueError("both samples need values")
    if len(set(a) | set(b)) == 1:  # every value tied: no evidence of a difference (scipy returns nan)
        return len(a) * len(b) / 2, 1.0
    r = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(r.statistic), float(r.pvalue)
