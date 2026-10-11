"""Reproduce one baseline paper's OWN evaluation (its figures, its instantiation) — not part of the comparison.

    python scripts/paper_reproduction.py s13_eaq_vrbc [--quick]
    python scripts/paper_reproduction.py all --quick

Parameters: configs/methods/<scheme>.yaml (reproduction); output: results/reproduction/<S id>/<what>.csv.
"""

import runpy
import sys

SCHEMES = ("s01_improved_dch", "s13_eaq_vrbc", "s27_etch", "s34_rebs")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in (*SCHEMES, "all"):
        sys.exit(__doc__)
    for scheme in SCHEMES if sys.argv[1] == "all" else [sys.argv[1]]:
        sys.argv = [scheme, *sys.argv[2:]]
        runpy.run_module(f"veredact_bench.methods.baselines.{scheme}.reproduce", run_name="__main__")
