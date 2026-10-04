"""Metrics against hand-computed values."""

import math

import pytest

from veredact_bench import metrics as M


def test_percentile_linear_interpolation():
    xs = [1, 2, 3, 4]
    assert M.percentile(xs, 50) == 2.5  # (n-1)*0.5 = 1.5 -> 2 + 0.5*(3-2)
    assert M.percentile(xs, 95) == pytest.approx(3.85)  # 3*0.95 = 2.85 -> 3 + 0.85*(4-3)
    assert M.percentile(xs, 0) == 1 and M.percentile(xs, 100) == 4
    assert M.median([5, 1, 3]) == 3
    with pytest.raises(ValueError):
        M.percentile([], 50)


def test_mean_std_ci():
    xs = [2, 4, 4, 4, 5, 5, 7, 9]
    assert M.mean(xs) == 5
    assert M.std(xs) == pytest.approx(math.sqrt(32 / 7))  # sum of squares 32, n - 1 = 7
    # t_{0.975, 7} = 2.364624 (Student t table)
    assert M.ci95_halfwidth(xs) == pytest.approx(2.364624 * math.sqrt(32 / 7) / math.sqrt(8), rel=1e-6)
    assert M.ci95_halfwidth([3]) == 0.0


def test_rates():
    assert M.throughput(120, 60) == 2.0
    assert M.per_thousand(5, 2000) == 2.5
    assert M.rate(1, 4) == 0.25 and M.rate(0, 0) == 0.0
    with pytest.raises(ValueError):
        M.throughput(1, 0)
