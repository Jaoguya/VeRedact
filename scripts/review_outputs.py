"""Review of the paper outputs: per figure, the numbers behind each line and why each line ends where it does.
Reads results/<exp>/<method>/<tier>/ only (no new measurement). Usage: scripts/review_outputs.py --tier experiment"""

# ruff: noqa: E501  (diagnostic report lines)
import argparse
import csv
import json
import statistics as st
from collections import defaultdict

from veredact_bench.utils.config import REPO_ROOT, load

R = REPO_ROOT / "results"
KEYS = ("veredact", "S1", "S13", "S27", "S34")


def med(xs):
    xs = [float(x) for x in xs if x not in ("", None)]
    return round(st.median(xs), 1) if xs else None


def exp1(tier):
    x = load(tier, "exp01_redaction_throughput")["experiment"]
    w0, w1 = x["warmup_s"], x["warmup_s"] + x["duration_s"]
    print(
        "== Fig. 3 — per rate: completions/s | executor crypto per batch (ms) and batch size | capacity = batch/crypto"
        " | ledger finality p50 | queue wait p50 | status mix of window arrivals"
    )
    for k in KEYS:
        d = R / "exp01_redaction_throughput" / k / tier
        if not (d / "rows.csv").exists():
            continue
        g = defaultdict(list)
        with open(d / "rows.csv") as f:
            for r in csv.DictReader(f):
                if r["sweep"] == "rate" and r["fault"] in ("", "None"):
                    g[float(r["rate_rps"])].append(r)
        for rate, rs in sorted(g.items()):
            comp = sum(
                1
                for r in rs
                if r["status"] == "finalized"
                and r["latency_ms"]
                and w0 <= float(r["submit_s"]) + float(r["latency_ms"]) / 1000 < w1
            )
            batches = {
                r["batch_id"]: (float(r["redact_crypto_ms"] or 0), int(r["batch_size"] or 0))
                for r in rs
                if r["batch_id"]
            }
            cms = med(v[0] for v in batches.values())
            bsz = med(v[1] for v in batches.values())
            cap = round(1000 * bsz / cms, 1) if cms and bsz else None
            mix = defaultdict(int)
            for r in rs:
                if r["in_window"] == "1":
                    mix[r["status"] + (":" + r["reason"][:22] if r["status"] == "rejected" else "")] += 1
            print(
                f"  {k:8s} {rate:6.0f}/s  done {comp / x['duration_s']:6.1f}/s | crypto/batch {cms} ms x {bsz} "
                f"-> cap {cap}/s | finality {med(r['finality_ledger_ms'] for r in rs)} ms | queue "
                f"{med(r['queue_ms'] for r in rs)} ms | {dict(mix)}"
            )
        info = json.loads((d / "run_info.json").read_text())
        print(f"     notes: {info.get('notes')}")


def metrics(exp, k, tier):
    p = R / exp / k / tier / "metrics.json"
    return json.loads(p.read_text())["points"] if p.exists() else {}


def generic(exp, title, fields):
    print(f"== {title}")
    for k in KEYS:
        pts = metrics(exp, k, tier=TIER)
        if not pts:
            continue
        for p, v in sorted(pts.items()):
            vals = {f: (v.get(f, {}).get("median") if isinstance(v.get(f), dict) else v.get(f)) for f in fields}
            print(f"  {k:8s} {p:45s} {vals}")
    for k in KEYS:
        rows = R / exp / k / TIER / "rows.csv"
        if rows.exists():
            with open(rows) as f:
                un = {
                    r.get("status")
                    for r in csv.DictReader(f)
                    if str(r.get("status", "")).startswith(("unreach", "NotSup"))
                }
            if un:
                print(f"  {k}: {sorted(un)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="experiment")
    TIER = ap.parse_args().tier
    exp1(TIER)
    generic("exp02_authorization_latency", "Fig. 4", ["auth_per_request_ms", "phase4_batch_ms"])
    generic("exp03_audit_efficiency", "Fig. 5", ["retrieval_ms", "evidence_bytes"])
    generic("exp04_verification_time", "Fig. 6", ["verify_ms", "verify_state_ms", "verify_attest_ms"])
    generic("exp05_gas_consumption", "Fig. 7", ["gas_per_round", "gas_per_redaction"])
