"""Run one or more paper experiments on one tier.

    python scripts/run_eval.py --tier smoke --experiment exp01_redaction_throughput
    python scripts/run_eval.py --tier experiment --config configs/experiments/exp02_authorization_latency.yaml
    python scripts/run_eval.py --tier pilot --experiment all [--force]

Results: results/<experiment>/<method>/<tier>/. A finished method (metrics.json present) is skipped
unless --force.
"""

import argparse
import os
from pathlib import Path

from veredact_bench.evaluation.runner import run
from veredact_bench.utils.config import TIERS, experiments


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", required=True, choices=TIERS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--experiment", nargs="+", choices=[*experiments(), "all"])
    g.add_argument("--config", nargs="+", type=Path, help="configs/experiments/<id>.yaml")
    ap.add_argument("--force", action="store_true", help="re-run methods whose metrics.json already exists")
    ap.add_argument("--systems", help="comma-separated subset of the experiments' systems (e.g. veredact)")
    a = ap.parse_args()
    if a.systems:
        os.environ["VRPQ_SYSTEMS"] = a.systems
    run(a.tier, a.experiment or [p.stem for p in a.config], a.force)


if __name__ == "__main__":
    main()
