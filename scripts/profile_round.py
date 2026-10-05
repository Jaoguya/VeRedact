"""Diagnostic (audit A3): where does one VeRedact-PQ execution round (Phase 4 + Phase 5) spend its time?
Builds a history in rounds of m requests (untimed driver, same code as Exp. 1's executor path) under cProfile
and prints the top functions plus per-primitive totals from the crypto counters.
Usage: scripts/profile_round.py --tier pilot --m 14 --requests 700 --zipf 0.0"""

import argparse
import cProfile
import io
import pstats
import time

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import build_history, open_system
from veredact_bench.utils.config import load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pilot")
    ap.add_argument("--m", type=int, default=14)
    ap.add_argument("--requests", type=int, default=700)
    ap.add_argument("--zipf", type=float, default=0.0)
    a = ap.parse_args()
    cfg = load(a.tier, "exp01_redaction_throughput")
    cfg["ledger"]["backend"] = "in_process"  # the round itself, not Besu
    ds = build_dataset(cfg, n_requests=a.requests, rate=100, zipf_s=a.zipf)
    s = open_system(cfg, "veredact", ds)
    s.crypto.reset()
    pr = cProfile.Profile()
    t = time.perf_counter()
    pr.enable()
    counts = build_history(s, [r for r in ds.trace if not r.fault], a.m)
    pr.disable()
    wall = time.perf_counter() - t
    rounds = max(1, counts["redacted"] // a.m)
    print(f"m={a.m} s={a.zipf}: {counts} in {wall:.1f} s -> {1000 * wall / rounds:.0f} ms per round (incl. requester proving)")
    print("crypto counters:", dict(s.crypto.counts))
    out = io.StringIO()
    pstats.Stats(pr, stream=out).sort_stats("tottime").print_stats(18)
    print(out.getvalue())


if __name__ == "__main__":
    main()
