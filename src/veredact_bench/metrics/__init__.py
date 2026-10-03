"""Metrics: pure functions (no I/O, no global state). Tables and figures compute every number through these.

One run per configuration point (configs/base.yaml): a point's statistics come from the samples inside
that run (every request in Exp. 1, every authorization batch / audit query in Exp. 2-4, every primitive
call in exp00). Confidence intervals use the normal approximation (samples_per_point >= 30 in the
experiment tier); comparisons between two systems use the Mann-Whitney U test (unpaired: two systems
never see the same request at the same time).
"""
import math
from collections.abc import Sequence

Z_975 = 1.959963984540054  # standard normal 0.975 quantile (two-sided 95%)


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
    """Half-width of the 95% CI of the mean (normal approximation)."""
    xs = _sorted(values)
    return Z_975 * std(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0


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
    """Two-sided Mann-Whitney U test. Returns (U of sample a, p-value).

    Normal approximation with tie correction and continuity correction; adequate for the sample sizes here
    (>= 20 per side). U counts pairs (x in a, y in b) with x > y, ties counting one half.
    """
    a, b = list(map(float, a)), list(map(float, b))
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("both samples need values")
    pooled = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks, ties, i = [0.0] * len(pooled), [], 0
    while i < len(pooled):  # average ranks over ties
        j = i
        while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = r
        if j > i:
            ties.append(j - i + 1)
        i = j + 1
    r1 = sum(r for r, (_, g) in zip(ranks, pooled) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    mu = n1 * n2 / 2
    var = n1 * n2 / 12 * ((n + 1) - sum(t ** 3 - t for t in ties) / (n * (n - 1)))
    if var == 0:
        return u1, 1.0
    z = (abs(u1 - mu) - 0.5) / math.sqrt(var)
    p = math.erfc(max(z, 0.0) / math.sqrt(2))  # two-sided
    return u1, min(1.0, p)
