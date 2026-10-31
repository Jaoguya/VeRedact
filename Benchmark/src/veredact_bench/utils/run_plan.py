"""Split full run (deploy/aws/launch_reps.sh, deploy/experiments/rep_run.sh): what each worker runs.

Fairness (configs/base.yaml environment): every experiment runs ALL its systems on ONE machine, so a run is split
by experiment, never by system. Hybrid plan (author 2026-10-31): one worker per part and run; the experiments in
config.ONCE (0 and 1) run in run 1 only, so later runs have no e1 worker.

    python -m veredact_bench.utils.run_plan experiments <part> [run]   -> experiment ids, space-separated
    python -m veredact_bench.utils.run_plan workers <runs>       -> one "<run(s)> <part>" line per worker
"""

import sys

from veredact_bench.utils.config import ONCE

PARTS = {
    "e1": ["exp01_redaction_throughput"],
    "e2": ["exp02_authorization_latency"],
    "e3": ["exp03_audit_efficiency"],
    "e4": ["exp04_verification_time"],
    "e05": ["exp00_primitives", "exp05_blockchain_overhead"],
}


def experiments_of(part: str, run: int | None = None) -> list[str]:
    """run None or 1: every experiment of the part; a later run leaves out ONCE."""
    return [e for e in PARTS[part] if run in (None, 1) or e not in ONCE]


def workers(runs: int) -> list[tuple[str, str]]:
    """(run label, part) per worker. One run: label "single" (results/.../experiment/); several: one worker per part
    and run that has an experiment left (results/.../experiment-repNN/)."""
    if runs == 1:
        return [("single", p) for p in PARTS]
    return [(str(r), p) for r in range(1, runs + 1) for p in PARTS if experiments_of(p, r)]


if __name__ == "__main__":
    what, arg = sys.argv[1:3]
    if what == "experiments":
        run = sys.argv[3] if len(sys.argv) > 3 else ""
        print(" ".join(experiments_of(arg, int(run) if run.isdigit() else None)))
    elif what == "workers":
        print("\n".join(f"{r} {p}" for r, p in workers(int(arg))))
    else:
        sys.exit(f"unknown command {what!r}: experiments <part> [run] | workers <runs>")
