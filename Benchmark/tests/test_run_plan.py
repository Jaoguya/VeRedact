"""Split full run (deploy/aws/launch_reps.sh): which worker runs what."""

import pytest

from veredact_bench.utils import run_plan
from veredact_bench.utils.config import experiments


def test_every_experiment_runs_on_exactly_one_part():
    """Fairness: an experiment's systems share one machine, so each experiment belongs to one part only."""
    owners = {e: [p for p in run_plan.PARTS if e in run_plan.experiments_of(p)] for e in experiments()}
    assert all(len(p) == 1 for p in owners.values()), owners


def test_hybrid_three_runs_run_exp0_and_exp1_once():
    """Hybrid plan (2026-10-31): one worker per part and run; Exp. 0 and 1 only in run 1, the rest in every run."""
    w = run_plan.workers(3)
    assert w[:5] == [("1", p) for p in ("e1", "e2", "e3", "e4", "e05")]
    assert w[5:] == [(str(r), p) for r in (2, 3) for p in ("e2", "e3", "e4", "e05")]
    assert run_plan.experiments_of("e05", 2) == ["exp05_blockchain_overhead"]
    assert run_plan.experiments_of("e1", 3) == []


def test_one_run_uses_the_single_run_folders():
    assert run_plan.workers(1) == [("single", p) for p in ("e1", "e2", "e3", "e4", "e05")]


def test_unknown_part_is_refused():
    with pytest.raises(KeyError):
        run_plan.experiments_of("e9")
