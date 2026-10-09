"""No-cap check (author rule 2026-10-05): every scheme of an experiment has a value at EVERY x point of its
figure. Reads results/<exp>/<method>/<tier>/metrics.json; prints one line per gap and exits 1 if any.
Usage: scripts/check_coverage.py --tier smoke"""

import argparse
import json
import sys

from veredact_bench.evaluation.results import method_dir
from veredact_bench.methods.registry import system_keys
from veredact_bench.utils.config import REPO_ROOT, load

R = REPO_ROOT / "results"


def pts(exp, key, tier):
    p = R / exp / method_dir(key) / tier / "metrics.json"  # veredact:no_bimc -> veredact-no_bimc
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

    def need(exp, key, want, field, inner=None, label=""):
        nonlocal checked
        checked += 1
        p = pts(exp, key, tier)
        if p is None:
            gaps.append(f"{exp} {key}: no metrics.json")
        elif not has(p, want, field, inner):
            gaps.append(f"{exp} {key}: no {field}{'.' + inner if inner else ''} at {want} {label}")

    x = load(tier, "exp01_redaction_throughput")
    e = x["experiment"]
    for key in system_keys(x):  # schemes + the experiment's VeRedact-PQ variants
        for rate in e["rates"]:
            need("exp01_redaction_throughput", key, {"sweep": "rate", "rate_rps": rate}, "throughput_per_s")
            need("exp01_redaction_throughput", key, {"sweep": "rate", "rate_rps": rate}, "latency_ms", "p95")
        for s in e["zipf_sweep"]:
            need("exp01_redaction_throughput", key, {"sweep": "skew", "zipf_s": s}, "pqch_adaptations_per_1000")
    x = load(tier, "exp02_authorization_latency")
    e = x["experiment"]
    for key in system_keys(x):
        for n in e["committee_sizes"]:
            for m in e["batch_sizes"]:
                at = {"committee_n": n, "batch_size": m}
                need("exp02_authorization_latency", key, at, "auth_per_request_ms", "median")
                need("exp02_authorization_latency", key, at, "batch_total_ms", "median")
    x = load(tier, "exp03_audit_efficiency")
    e = x["experiment"]
    for key in system_keys(x):
        for rpb in e["records_per_batch"] if key.startswith("veredact") else [None]:
            for n in e["n_Q"]:
                at = {"n_Q": n} | ({"records_per_batch": rpb} if rpb else {})
                need("exp03_audit_efficiency", key, at, "retrieval_ms", "median")
    x = load(tier, "exp04_verification_time")
    e = x["experiment"]
    for key in system_keys(x):
        for level in e["levels"] if key.startswith("veredact") else ["normal"]:
            for n in e["n_Q"]:
                need("exp04_verification_time", key, {"n_Q": n, "level": level}, "verify_ms", "median")
    x = load(tier, "exp05_gas_consumption")
    e = x["experiment"]
    gas_field = "gas_per_redaction" if x["ledger"]["backend"] == "besu" else "redactions"  # in_process: no receipts
    for key in system_keys(x):
        for s in e["zipf_sweep"]:
            for m in e["batch_sizes"]:
                need("exp05_gas_consumption", key, {"zipf_s": s, "batch_size": m}, gas_field)
    for g in gaps:
        print("GAP", g)
    print(f"coverage {tier}: {checked - len(gaps)}/{checked} (scheme, x) points have a value; {len(gaps)} gaps")
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
