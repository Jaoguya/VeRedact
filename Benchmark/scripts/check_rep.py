"""Sanity gate after one repetition of the full run (deploy/experiments/rep_sequence.sh): the next repetition
starts only if every check passes, so a fault is fixed before more runs are paid for. Checks the results of
VRPQ_REP's folder (<tier>-repNN): logic that must hold whatever the numbers are, never a target value.
  1 every (scheme, x) point of every figure has a value          (scripts/check_coverage.py does the listing)
  2 Exp. 1 p95 end-to-end latency never falls as the arrival rate rises (3 % tolerance: saturated lower bounds)
  3 Exp. 2 every valid request is authorized
  4 Exp. 4 per-record schemes (VeRedact-PQ, S1) never reject a valid record and detect every injected one
  5 Exp. 5 every scheme has gas at every batch size
  6 no Python traceback in the repetition's run logs
Usage: VRPQ_REP=r scripts/check_rep.py --tier experiment [--logs results/logs/rep_rNN.out]"""

import argparse
import json
import subprocess
import sys

from veredact_bench.utils.config import REPO_ROOT, load, results_tier

R = REPO_ROOT / "results"


def metrics(exp, key, tier):
    p = R / exp / key / results_tier(tier) / "metrics.json"
    return json.loads(p.read_text())["points"] if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="experiment")
    ap.add_argument("--logs", nargs="*", default=[])
    a = ap.parse_args()
    fail = []
    cov = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "check_coverage.py"), "--tier", a.tier])
    if cov.returncode:
        fail.append("coverage: gaps (see GAP lines above)")
    e1 = load(a.tier, "exp01_redaction_throughput")["experiment"]
    for key in e1["systems"]:
        pts = metrics("exp01_redaction_throughput", key, a.tier) or {}
        p95 = sorted(
            (float(k.split("|")[1].split("=")[1]), v["latency_ms"].get("p95"))
            for k, v in pts.items()
            if k.startswith("sweep=rate")
        )
        for (r0, y0), (r1, y1) in zip(p95, p95[1:]):
            if y0 is not None and y1 is not None and y1 < 0.97 * y0:
                fail.append(f"exp1 {key}: p95 {y0 / 1e3:.1f} s at {r0:g} req/s -> {y1 / 1e3:.1f} s at {r1:g} req/s")
    for key in load(a.tier, "exp02_authorization_latency")["experiment"]["systems"]:
        for k, v in (metrics("exp02_authorization_latency", key, a.tier) or {}).items():
            if v["accepted"] != v["requests"]:
                fail.append(f"exp2 {key} {k}: {v['accepted']} of {v['requests']} valid requests authorized")
    for key in ("veredact", "S1"):
        for k, v in (metrics("exp04_verification_time", key, a.tier) or {}).items():
            if v.get("status") != "ok":
                continue
            if v["false_rejection_rate"]:
                fail.append(f"exp4 {key} {k}: false rejection rate {v['false_rejection_rate']}")
            if v["detection_rate"] not in (None, 1.0):
                fail.append(f"exp4 {key} {k}: detection rate {v['detection_rate']}")
    for key in load(a.tier, "exp05_blockchain_overhead")["experiment"]["systems"]:
        for k, v in (metrics("exp05_blockchain_overhead", key, a.tier) or {}).items():
            if not v["finalize_ms"].get("n"):
                fail.append(f"exp5 {key} {k}: no finalization latency")
    for log in a.logs:
        text = open(log, errors="replace").read()
        if "Traceback (most recent call last)" in text:
            fail.append(f"traceback in {log}")
    for f in fail:
        print("FAIL", f)
    print(f"check_rep {results_tier(a.tier)}: {'PASS' if not fail else f'{len(fail)} failure(s)'}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
