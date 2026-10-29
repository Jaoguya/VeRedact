"""Split full run (deploy/aws/launch_reps.sh, deploy/experiments/rep_run.sh): what each worker runs.

Fairness (configs/base.yaml environment): every experiment runs ALL its systems on ONE machine, so a run is split
by experiment, never by system. Experiment 1 goes to [run] e1_machines workers, each with its own prover pair; a
run's Experiment 1 is on exactly one of them (runs dealt round-robin: 1,3 | 2). Author 2026-10-30, final plan.

    python -m veredact_bench.utils.run_plan experiments <part>   -> experiment ids, space-separated
    python -m veredact_bench.utils.run_plan workers <runs>       -> one "<run(s)> <part>" line per worker
"""

import sys
import tomllib

from veredact_bench.utils.config import REPO_ROOT

PARTS = {
    "e1": ["exp01_redaction_throughput"],
    "e2": ["exp02_authorization_latency"],
    "e3": ["exp03_audit_efficiency"],
    "e4": ["exp04_verification_time"],
    "e05": ["exp00_primitives", "exp05_blockchain_overhead"],
}


def experiments_of(part: str) -> list[str]:
    return PARTS[part]


def e1_machines() -> int:
    return tomllib.loads((REPO_ROOT / "configs" / "aws.toml").read_text())["run"]["e1_machines"]


def workers(runs: int) -> list[tuple[str, str]]:
    """(run label, part) per worker, the e1 workers first. One run: label "single" (results/.../experiment/);
    several: e1 worker k gets runs k, k + m, ... (m = e1_machines), every other part one worker per run
    (results/.../experiment-repNN/)."""
    if runs == 1:
        return [("single", p) for p in PARTS]
    m = min(e1_machines(), runs)
    e1 = [(",".join(str(r) for r in range(k, runs + 1, m)), "e1") for k in range(1, m + 1)]
    return e1 + [(str(r), p) for r in range(1, runs + 1) for p in PARTS if p != "e1"]


if __name__ == "__main__":
    what, arg = sys.argv[1:3]
    if what == "experiments":
        print(" ".join(experiments_of(arg)))
    elif what == "workers":
        print("\n".join(f"{r} {p}" for r, p in workers(int(arg))))
    else:
        sys.exit(f"unknown command {what!r}: experiments <part> | workers <runs>")
