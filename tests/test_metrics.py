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


def test_mann_whitney_hand_computed():
    # a = [1, 2, 3], b = [4, 5, 6]: no pair with a > b -> U_a = 0. Exact test (no ties, small n): of the
    # C(6,3) = 20 equally likely rank splits, U = 0 and U = 9 are as extreme -> two-sided p = 2/20 = 0.1
    u, p = M.mann_whitney_u([1, 2, 3], [4, 5, 6])
    assert u == 0
    assert p == pytest.approx(0.1)


def test_mann_whitney_ties_and_symmetry():
    a, b = [1, 2, 2, 3], [2, 3, 4, 5]
    # pairs a > b: (3>2) = 1; ties count 1/2: (2,2) x2 + (3,3) x1 -> 1.5; U_a = 2.5
    u, p = M.mann_whitney_u(a, b)
    assert u == pytest.approx(2.5)
    u2, p2 = M.mann_whitney_u(b, a)
    assert u + u2 == pytest.approx(len(a) * len(b)) and p == pytest.approx(p2)
    # ties -> normal approximation: mu = 8, tie-corrected var = 16/12*(9 - 30/56) = 11.2857, continuity 0.5
    assert p == pytest.approx(math.erfc(((8 - 2.5) - 0.5) / math.sqrt(16 / 12 * (9 - 30 / 56)) / math.sqrt(2)))
    assert M.mann_whitney_u([1, 1], [1, 1])[1] == 1.0  # all tied: no evidence
