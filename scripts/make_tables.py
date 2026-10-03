"""results/ -> paper/tables/*.tex (booktabs):  python scripts/make_tables.py --tier experiment"""
import argparse

from veredact_bench.reporting.tables import make_all
from veredact_bench.utils.config import TIERS
from veredact_bench.utils.log import get_logger

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", required=True, choices=TIERS)
    for path in make_all(ap.parse_args().tier):
        get_logger().info(f"-> {path}")
