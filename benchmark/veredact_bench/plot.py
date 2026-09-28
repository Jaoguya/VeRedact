"""Render the paper's Figs. 3-7 from results/*.csv (file names match the \\includegraphics in VeRedact.tex).

Usage: python -m veredact_bench.plot [results_dir] [plot_dir]   (defaults: <repo>/results, <repo>/plot)
"""
import csv
import os
import sys
from collections import defaultdict

import matplotlib

from .config import PLOTS_DIR, RESULTS_DIR

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def series(rows, x, y, key="scheme", where=None):
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if where and any(r.get(k) != v for k, v in where.items()):
            continue
        try:
            acc[r[key]][float(r[x])].append(float(r[y]))
        except (ValueError, KeyError):
            continue
    return {k: sorted((xx, sum(v) / len(v)) for xx, v in d.items()) for k, d in acc.items()}


def draw(ax, data, xlabel, ylabel, logx=False, logy=False):
    for name, pts in sorted(data.items()):
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=3, label=name)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=6)


def main(res=RESULTS_DIR, figs=PLOTS_DIR):
    os.makedirs(figs, exist_ok=True)
    r1 = load(f"{res}/exp1_throughput_latency.csv")
    if r1:
        f, ax = plt.subplots(1, 3, figsize=(13, 3.6))
        draw(ax[0], series(r1, "rate", "throughput", where={"sweep": "rate"}), "arrival rate (req/s)", "throughput (redactions/s)")
        draw(ax[1], series(r1, "rate", "lat_p95", where={"sweep": "rate"}), "arrival rate (req/s)", "p95 latency (s)")
        draw(ax[2], series(r1, "zipf", "adapt_per_1000", where={"sweep": "zipf"}), "Zipf skew s", "PQCH adaptations / 1000")
        f.tight_layout()
        f.savefig(f"{figs}/exp1_redaction_throughput.png", dpi=200)
    r2 = load(f"{res}/exp2_authorization.csv")
    if r2:
        f, ax = plt.subplots(1, 2, figsize=(9, 3.6))
        draw(ax[0], series(r2, "m", "per_request_ms", where={"n": "7"}), "batch size m", "amortized latency / request (ms)", logx=True, logy=True)
        draw(ax[1], series(r2, "n", "batch_ms", where={"m": "64"}), "committee size n", "per-batch latency (ms)")
        f.tight_layout()
        f.savefig(f"{figs}/exp2_authorization_latency.png", dpi=200)
    r3 = load(f"{res}/exp3_audit_efficiency.csv")
    if r3:
        f, ax = plt.subplots(1, 2, figsize=(9, 3.6))
        base = [r for r in r3 if r["records_per_batch"] in ("16", "-")]
        draw(ax[0], series(base, "n_Q", "gen_ms_mean"), "returned records n_Q", "response generation (ms)", True, True)
        draw(ax[1], series(base, "n_Q", "resp_bytes"), "returned records n_Q", "response size (bytes)", True, True)
        f.tight_layout()
        f.savefig(f"{figs}/exp3_audit_efficiency.png", dpi=200)
    r4 = load(f"{res}/exp4_verification.csv")
    if r4:
        f, ax = plt.subplots(1, 2, figsize=(9, 3.6))
        rows = [dict(r, scheme=f"{r['scheme']} ({r['instantiation']}, {r['level']})") for r in r4 if r["level"] != "inject"]
        draw(ax[0], series(rows, "n_Q", "ver_ms_mean"), "verified records n_Q", "verification time (ms)", True, True)
        vr = [r for r in r4 if r["scheme"] == "VeRedact-PQ" and r["level"] == "normal"]
        if vr:
            last = vr[-1]
            parts = {k[3:]: float(v) for k, v in last.items() if k.startswith("ms_") and v}
            ax[1].bar(list(parts), list(parts.values()))
            ax[1].set_ylabel(f"ms (n_Q={last['n_Q']}, normal audit)")
            ax[1].tick_params(axis="x", rotation=45)
        f.tight_layout()
        f.savefig(f"{figs}/exp4_verification_time.png", dpi=200)
    r5 = load(f"{res}/exp5_gas.csv")
    if r5:
        f, ax = plt.subplots(1, 2, figsize=(9, 3.6))
        rows = [dict(r, scheme=f"{r['scheme']} (s={r['zipf']})") for r in r5 if r["op"] == "authorization round"]
        draw(ax[0], series(rows, "m", "gas_total"), "redactions per batch m", "gas per authorization round", True, True)
        draw(ax[1], series(rows, "m", "gas_per_redaction"), "redactions per batch m", "gas per redaction", True, True)
        f.tight_layout()
        f.savefig(f"{figs}/exp5_gas_consumption.png", dpi=200)
    print(f"figures written to {figs}/")


if __name__ == "__main__":
    main(*sys.argv[1:])
