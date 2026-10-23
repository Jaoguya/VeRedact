"""No-cap check (author rule 2026-10-05): every scheme of an experiment has a value at EVERY x point of its
figure. Reads results/<exp>/<method>/<tier>/metrics.json; prints one line per gap and exits 1 if any.
Usage: scripts/check_coverage.py --tier smoke"""

import argparse
import json
import os
import sys

from veredact_bench.utils.config import REPO_ROOT, exp1_rates, load, results_tier

R = REPO_ROOT / "results"


def pts(exp, key, tier):
    p = R / exp / key / results_tier(tier) / "metrics.json"  # VRPQ_REP=r: the repetition's folder
    return json.loads(p.read_text())["points"] if p.exists() else None


def _forms(b) -> set:
    """How a value can appear in a point key: 100 / 100.0 for numbers, as is for text."""
    try:
        return {str(b), str(float(b)), str(int(float(b)))} if float(b) == int(float(b)) else {str(b), str(float(b))}
    except (TypeError, ValueError):
        return {str(b)}


def has(points, want: dict, field: str, inner=None):
    """A point whose key contains every want=value pair and whose field is a real number."""
    for k, v in points.items():
        kv = dict(p.split("=", 1) for p in k.split("|"))
        if all(str(kv.get(a)) in _forms(b) for a, b in want.items()):
            x = v.get(field)
            x = x.get(inner) if isinstance(x, dict) and inner else x
            if x is not None:
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="smoke")
    tier = ap.parse_args().tier
    gaps, checked = [], 0

    # VRPQ_SKIP="exp:system,...": pairs another server owns in a repeated run (as run_eval skips them)
    skip = {tuple(p.split(":", 1)) for p in os.environ.get("VRPQ_SKIP", "").split(",") if ":" in p}

    def need(exp, key, want, field, inner=None, label=""):
        nonlocal checked
        if (exp, key) in skip:
            return
        checked += 1
        p = pts(exp, key, tier)
        if p is None:
            gaps.append(f"{exp} {key}: no metrics.json")
        elif not has(p, want, field, inner):
            gaps.append(f"{exp} {key}: no {field}{'.' + inner if inner else ''} at {want} {label}")

    x = load(tier, "exp01_redaction_throughput")
    e = x["experiment"]
    for key in e["systems"]:
        for rate in exp1_rates(e, key):
            need("exp01_redaction_throughput", key, {"sweep": "rate", "rate_rps": rate}, "throughput_per_s")
            need("exp01_redaction_throughput", key, {"sweep": "rate", "rate_rps": rate}, "latency_ms", "p95")
        for s in e["zipf_sweep"]:
            need("exp01_redaction_throughput", key, {"sweep": "skew", "zipf_s": s}, "pqch_adaptations_per_1000")
    x = load(tier, "exp02_authorization_latency")
    e = x["experiment"]
    for key in e["systems"]:
        for n in e["committee_sizes"]:
            for m in e["batch_sizes"]:
                at = {"committee_n": n, "batch_size": m}
                need("exp02_authorization_latency", key, at, "auth_per_request_ms", "median")
                need("exp02_authorization_latency", key, at, "batch_total_ms", "median")
    for exp in ("exp03_audit_efficiency", "exp04_verification_time"):
        e = load(tier, exp)["experiment"]
        field = "retrieval_ms" if exp.startswith("exp03") else "verify_ms"
        for key in e["systems"]:
            for n in e["n_Q"]:
                need(exp, key, {"n_Q": n}, field, "median")
        # one dataset and one history request list for every scheme of the experiment (author rule 2026-10-19)
        seen = {}
        for key in e["systems"]:
            info = R / exp / key / results_tier(tier) / "run_info.json"
            p = pts(exp, key, tier)
            if p is None or not info.exists():
                continue
            ds = tuple(json.loads(info.read_text()).get("dataset_ids", []))
            hs = tuple(sorted({v.get("history_id") for v in p.values() if v.get("history_id")}))
            seen[key] = (ds, hs)
        if len(set(seen.values())) > 1:
            gaps.append(f"{exp}: schemes differ in dataset / history: {seen}")
    x = load(tier, "exp05_gas_consumption")
    e = x["experiment"]
    gas_field = "gas_per_redaction" if x["ledger"]["backend"] == "besu" else "redactions"  # in_process: no receipts
    for key in e["systems"]:
        for s in e["zipf_sweep"]:
            for m in e["batch_sizes"]:
                need("exp05_gas_consumption", key, {"zipf_s": s, "batch_size": m}, gas_field)
    for g in gaps:
        print("GAP", g)
    print(f"coverage {tier}: {checked - len(gaps)}/{checked} (scheme, x) points have a value; {len(gaps)} gaps")
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
