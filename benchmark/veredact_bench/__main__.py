"""CLI: python -m veredact_bench exp1 [exp2 ...] [--quick] [--out results]"""
import argparse
import time

from .config import RESULTS_DIR, RunConfig
from .experiments import ALL


def main():
    ap = argparse.ArgumentParser(description="VeRedact-PQ evaluation harness")
    ap.add_argument("experiments", nargs="+", choices=[*ALL, "all"])
    ap.add_argument("--quick", action="store_true", help="small ledger, 3 reps, trimmed sweeps (smoke run)")
    ap.add_argument("--out", default=RESULTS_DIR, help="CSV output dir (default: <repo>/results)")
    a = ap.parse_args()
    cfg = RunConfig.from_args(a.quick, a.out)
    for name in (list(ALL) if "all" in a.experiments else a.experiments):
        print(f"=== {name} (quick={cfg.quick}, reps={cfg.reps}, ledger={cfg.ledger_size}) ===", flush=True)
        t = time.time()
        ALL[name](cfg)
        print(f"=== {name} done in {time.time() - t:.1f}s ===", flush=True)


if __name__ == "__main__":
    main()
