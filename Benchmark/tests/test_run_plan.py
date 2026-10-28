"""Split full run (deploy/aws/launch_reps.sh): which worker runs what."""

import pytest

from veredact_bench.utils import run_plan
from veredact_bench.utils.config import experiments


def test_every_experiment_runs_on_exactly_one_part():
    """Fairness: an experiment's systems share one machine, so each experiment belongs to one part only."""
    owners = {e: [p for p in run_plan.PARTS if e in run_plan.experiments_of(p)] for e in experiments()}
    assert all(len(p) == 1 for p in owners.values()), owners


def test_three_runs_put_every_runs_exp1_on_one_machine():
    """Layout (a): one e1 worker for all runs (the one prover pair serves it run after run), one worker per
    other part and run."""
    w = run_plan.workers(3)
    assert w[0] == ("1,2,3", "e1")
    rest = [x for x in w if x[1] != "e1"]
    assert sorted(rest) == sorted((str(r), p) for r in (1, 2, 3) for p in ("e2", "e3", "e4", "e05"))
    assert len(w) == 13


def test_one_run_uses_the_single_run_folders():
    assert run_plan.workers(1) == [("single", p) for p in ("e1", "e2", "e3", "e4", "e05")]


def test_unknown_part_is_refused():
    with pytest.raises(KeyError):
        run_plan.experiments_of("e9")
