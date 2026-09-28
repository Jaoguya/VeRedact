"""Render manuscript Figs. 3-7 from the newest run of each experiment (results/<exp>/<run_id>/rows.csv).

File names match the \\includegraphics in overleaf/VeRedact.tex. Each figure prints the run id it was drawn
from and the capability matrix of the systems in it (generated from the rows, i.e. from the code), so a
figure can never be read without knowing what each system can and cannot do.

Usage: python -m veredact_bench.plot [results_dir] [plot_dir]   (defaults: <repo>/results, <repo>/plot)
"""
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

from .config import REPO_ROOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def latest(res: Path, exp: str):
    runs = sorted(p for p in (res / exp).glob("*") if (p / "rows.csv").exists())
    if not runs:
        return None, []
    with open(runs[-1] / "rows.csv") as f:
        return runs[-1].name, list(csv.DictReader(f))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def series(rows, x, y, key="system", where=None, agg=statistics.median):
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if where and not where(r):
            continue
        xv, yv = num(r.get(x)), num(r.get(y))
        if xv is not None and yv is not None:
            acc[r[key]][xv].append(yv)
    return {k: sorted((xv, agg(ys)) for xv, ys in d.items()) for k, d in acc.items()}


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))]


def draw(ax, data, xlabel, ylabel, logx=False, logy=False, title=""):
    for name, pts in sorted(data.items()):
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=3, label=name)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9)
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
    ax.grid(alpha=0.3)
    if data:
        ax.legend(fontsize=6)


def caption(fig, run, rows):
    caps = {}
    for r in rows:
        caps.setdefault(r["system"], "".join("✓" if r.get(k) == "1" else "·" for k in sorted(r) if k.startswith("cap_")))
    keys = sorted(k[4:] for k in rows[0] if k.startswith("cap_")) if rows else []
    txt = f"run {run} | capabilities [{', '.join(keys)}]: " + "  ".join(f"{s}:{c}" for s, c in sorted(caps.items()))
    fig.text(0.01, 0.005, txt, fontsize=5)


def save(fig, out: Path, name: str):
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / name, dpi=200)
    plt.close(fig)
    print(f"-> {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}/{name}")


def main(res: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)

    run, rows = latest(res, "exp1")
    if rows:
        rate_rows = lambda r: r.get("sweep") == "rate" and r["in_window"] == "1" and r["status"] == "finalized"
        f, ax = plt.subplots(1, 3, figsize=(13, 3.6))
        draw(ax[0], series(rows, "rate_rps", "latency_ms", where=rate_rows), "offered rate (req/s)", "p50 latency (ms)", True, True)
        draw(ax[1], series(rows, "rate_rps", "latency_ms", where=rate_rows, agg=p95), "offered rate (req/s)", "p95 latency (ms)", True, True)
        good = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if rate_rows(r):
                good[r["system"]][(float(r["rate_rps"]), r["rep"])] += 1
        dur = json.loads((res / "exp1" / run / "manifest.json").read_text())["resolved_config"]["experiments"]["exp1"]["duration_s"]
        draw(ax[2], {s: sorted((x, statistics.mean(v / dur for (xx, _), v in d.items() if xx == x))
                               for x in {k[0] for k in d}) for s, d in good.items()},
             "offered rate (req/s)", "goodput (redactions/s)", True, True)
        caption(f, run, rows)
        save(f, out, "exp1_redaction_throughput.png")

    run, rows = latest(res, "exp2")
    if rows:
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(rows, "committee_n", "auth_per_request_ms", where=lambda r: r["batch_size"] == "1"),
             "committee size n (t = floor(2n/3)+1)", "authorization per request (ms)", logy=True, title="b = 1")
        draw(ax[1], series(rows, "batch_size", "auth_per_request_ms", key="system",
                           where=lambda r: r["system"].startswith("veredact") and r["committee_n"] == "7"),
             "ABRRR batch size b", "amortised per request (ms)", True, True, title="n = 7")
        caption(f, run, rows)
        save(f, out, "exp2_authorization_latency.png")

    run, rows = latest(res, "exp3")
    if rows:
        ok = [r for r in rows if r.get("status") == "ok"]
        lab = lambda r: {**r, "system": f"{r['system']} rpb={r['records_per_batch']}"}
        ok = [lab(r) for r in ok]
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(ok, "n_Q", "retrieval_ms"), "returned records n_Q", "response generation (ms)", True, True)
        draw(ax[1], series(ok, "n_Q", "evidence_bytes"), "returned records n_Q", "response size (bytes)", True, True)
        caption(f, run, ok)
        save(f, out, "exp3_audit_efficiency.png")

    run, rows = latest(res, "exp4")
    if rows:
        ok = [{**r, "system": f"{r['system']} ({r['level']})"} for r in rows if r.get("status") == "ok"]
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(ok, "n_Q", "verify_ms", where=lambda r: num(r["inject_fraction"]) == 0), "verified records n_Q",
             "verification time (ms)", True, True, title="clean")
        draw(ax[1], series(ok, "inject_fraction", "false_rejections", agg=statistics.mean), "injected fraction",
             "valid records falsely rejected", title="granularity")
        caption(f, run, ok)
        save(f, out, "exp4_verification_time.png")

    run, rows = latest(res, "exp5")
    if rows and any(r["gas_used"] for r in rows):
        f, ax = plt.subplots(1, 1, figsize=(5.5, 3.6))
        draw(ax, series(rows, "batch_size", "gas_per_redaction", where=lambda r: r["zipf_s"] == rows[0]["zipf_s"]),
             "batch size b", "gas per redaction", True, True)
        caption(f, run, rows)
        save(f, out, "exp5_gas_consumption.png")
    elif rows:
        print("exp5: no receipts (in_process ledger) — no gas figure drawn")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "results",
         Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT / "plot")
