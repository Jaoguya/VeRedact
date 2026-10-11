"""Recompute metrics.json from the stored rows.csv with the current summaries (rows are the source of truth).

Used when a metric's DEFINITION changes but the measurement does not (2026-10-05: Exp. 1 throughput = redactions
finalized during the window). The old metrics.json is kept as metrics.prev.json; run_info.json records it.
Usage: scripts/resummarize.py --tier experiment --experiment exp01_redaction_throughput
"""

import argparse
import csv
import json
import time

from veredact_bench.evaluation.summaries import summarize
from veredact_bench.utils.config import REPO_ROOT, load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True)
    ap.add_argument("--experiment", nargs="+", required=True)
    a = ap.parse_args()
    for exp in a.experiment:
        for d in sorted((REPO_ROOT / "results" / exp).glob(f"*/{a.tier}")):
            if not (d / "rows.csv").exists():
                continue
            cfg = load(a.tier, exp)
            with open(d / "rows.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            m = d / "metrics.json"
            if m.exists() and not (d / "metrics.prev.json").exists():
                m.rename(d / "metrics.prev.json")
            m.write_text(json.dumps(summarize(exp, rows, cfg), indent=2, default=str))
            info = json.loads((d / "run_info.json").read_text())
            info.setdefault("resummarized_utc", []).append(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            (d / "run_info.json").write_text(json.dumps(info, indent=2, default=str))
            print(f"{d.relative_to(REPO_ROOT)}: metrics.json recomputed from {len(rows)} rows")


if __name__ == "__main__":
    main()
