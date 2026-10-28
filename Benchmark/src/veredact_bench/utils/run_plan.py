"""Split full run (deploy/aws/launch_reps.sh, deploy/experiments/rep_run.sh): what each worker runs.

Fairness (configs/base.yaml environment): every experiment runs ALL its systems on ONE machine, so a run is split
by experiment, never by system. Experiment 1 of every run goes to one e1 worker: the single prover pair the quota
allows serves its VeRedact-PQ systems run after run (author 2026-10-28, layout (a)).

    python -m veredact_bench.utils.run_plan experiments <part>   -> experiment ids, space-separated
    python -m veredact_bench.utils.run_plan workers <runs>       -> one "<run(s)> <part>" line per worker
"""

import sys

PARTS = {
    "e1": ["exp01_redaction_throughput"],
    "e2": ["exp02_authorization_latency"],
    "e3": ["exp03_audit_efficiency"],
    "e4": ["exp04_verification_time"],
    "e05": ["exp00_primitives", "exp05_blockchain_overhead"],
}


def experiments_of(part: str) -> list[str]:
    return PARTS[part]


def workers(runs: int) -> list[tuple[str, str]]:
    """(run label, part) per worker, e1 first. One run: label "single" (results/.../experiment/); several:
    e1 gets "1,2,...", every other part one worker per run (results/.../experiment-repNN/)."""
    if runs == 1:
        return [("single", p) for p in PARTS]
    return [(",".join(str(r) for r in range(1, runs + 1)), "e1")] + [
        (str(r), p) for r in range(1, runs + 1) for p in PARTS if p != "e1"
    ]


if __name__ == "__main__":
    what, arg = sys.argv[1:3]
    if what == "experiments":
        print(" ".join(experiments_of(arg)))
    elif what == "workers":
        print("\n".join(f"{r} {p}" for r, p in workers(int(arg))))
    else:
        sys.exit(f"unknown command {what!r}: experiments <part> | workers <runs>")
