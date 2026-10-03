"""Render manuscript Figs. 3-7 from the newest run of each experiment (results/<exp>/<run_id>/rows.csv),
plus the table sources plot/primitives_table.csv (tab:primitives) and plot/gas_by_operation.csv (tab:gas).

Figure panels follow the manuscript captions; file names match the \\includegraphics in the manuscript. Each figure prints the run id it was drawn
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
        # (a) throughput and (b) p95 end-to-end latency vs arrival rate; (c) PQCH adaptations per 1,000
        # finalized redactions vs Zipf skew
        f, ax = plt.subplots(1, 3, figsize=(13, 3.6))
        good = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if rate_rows(r):
                good[r["system"]][(float(r["rate_rps"]), r["rep"])] += 1
        dur = json.loads((res / "exp1" / run / "manifest.json").read_text())["resolved_config"]["experiments"]["exp1"]["duration_s"]
        draw(ax[0], {s: sorted((x, statistics.mean(v / dur for (xx, _), v in d.items() if xx == x))
                               for x in {k[0] for k in d}) for s, d in good.items()},
             "offered rate (req/s)", "throughput (finalized redactions/s)", True, True)
        draw(ax[1], series(rows, "rate_rps", "latency_ms", where=rate_rows, agg=p95), "offered rate (req/s)",
             "p95 end-to-end latency (ms)", True, True)
        adapt = defaultdict(lambda: defaultdict(dict))  # system -> (skew, rep) -> {batch_id: adaptations}
        fin = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r.get("sweep") == "skew" and r["status"] == "finalized" and r["batch_id"] != "":
                k = (float(r["zipf_s"]), r["rep"])
                adapt[r["system"]][k][r["batch_id"]] = float(r["batch_adaptations"])
                fin[r["system"]][k] += 1
        per_k = {s: sorted((z, statistics.mean(1000 * sum(adapt[s][(zz, rep)].values()) / fin[s][(zz, rep)]
                                               for (zz, rep) in d if zz == z)) for z in {k[0] for k in d})
                 for s, d in adapt.items()}
        draw(ax[2], per_k, "Zipf skew s", "PQCH adaptations per 1,000 redactions")
        caption(f, run, rows)
        save(f, out, "exp1_redaction_throughput.png")

    run, rows = latest(res, "exp2")
    if rows:
        # (a) amortized latency per request vs batch size; (b) per-batch latency vs committee size
        cfg = json.loads((res / "exp2" / run / "manifest.json").read_text())["resolved_config"]
        n0, b0 = str(cfg["veredact"]["committee_n"]), str(cfg["veredact"]["fixed_batch"])
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(rows, "batch_size", "auth_per_request_ms", where=lambda r: r["committee_n"] == n0
                           and (r["system"].startswith("veredact") or r["batch_size"] == "1")),
             "ABRRR batch size m", "amortized per request (ms)", True, True, title=f"n = {n0}")
        # one batch: VeRedact-PQ's Phase 4 for an m = fixed_batch batch; baselines authorize one request per batch
        per_batch = [{**r, "batch_ms": r["phase4_batch_ms"] if r["system"].startswith("veredact") else r["auth_per_request_ms"]}
                     for r in rows if (r["batch_size"] == b0 if r["system"].startswith("veredact") else r["batch_size"] == "1")]
        draw(ax[1], series(per_batch, "committee_n", "batch_ms"), "committee size n (t = floor(2n/3)+1)",
             "per-batch authorization (ms)", logy=True, title=f"VeRedact-PQ m = {b0}")
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
        # (a) total verification time vs n_Q, normal and deep audits; (b) verification-time breakdown
        ok = [{**r, "system": f"{r['system']} ({r['level']})"} for r in rows if r.get("status") == "ok"]
        clean = [r for r in ok if num(r["inject_fraction"]) == 0]
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(clean, "n_Q", "verify_ms"), "verified records n_Q", "verification time (ms)", True, True)
        parts = ("response_ms", "rai_mp_ms", "committee_ms", "attest_ms", "state_ms", "zk_ms")
        names = ("response + query", "RAI multiproof", "committee approvals", "attestations", "state + PQCH", "PQZK")
        vr = [r for r in clean if r["system"].startswith("veredact (") and r.get("verify_response_ms") not in ("", None)]
        n_max = max((int(r["n_Q"]) for r in vr), default=0)
        levels = sorted({r["level"] for r in vr})
        bottom = [0.0] * len(levels)
        for p, nm in zip(parts, names):
            h = [statistics.median(num(r[f"verify_{p}"]) for r in vr if r["level"] == lv and int(r["n_Q"]) == n_max)
                 for lv in levels]
            ax[1].bar(levels, h, bottom=bottom, label=nm)
            bottom = [a + b for a, b in zip(bottom, h)]
        ax[1].set_ylabel("verification time (ms)")
        ax[1].set_title(f"VeRedact-PQ, n_Q = {n_max}", fontsize=8)
        ax[1].legend(fontsize=6)
        caption(f, run, ok)
        save(f, out, "exp4_verification_time.png")
        # granularity (text of Exp. 4): valid records falsely rejected vs injected fraction
        f, ax = plt.subplots(1, 1, figsize=(5.5, 3.6))
        draw(ax, series(ok, "inject_fraction", "false_rejections", agg=statistics.mean), "injected fraction",
             "valid records falsely rejected")
        caption(f, run, ok)
        save(f, out, "exp4_granularity.png")

    run, rows = latest(res, "exp5")
    if rows and any(r["gas_used"] for r in rows):
        # (a) total gas per authorization round and (b) amortized gas per redaction vs redactions per batch,
        # one series per (system, skew); a baseline's round of m redactions costs m times its per-redaction gas
        lab = [{**r, "system": f"{r['system']} s={r['zipf_s']}",
                "round_gas": num(r["gas_per_redaction"]) * num(r["batch_size"])} for r in rows if r["gas_per_redaction"]]
        f, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        draw(ax[0], series(lab, "batch_size", "round_gas"), "redactions per batch m", "total gas per round", True, True)
        draw(ax[1], series(lab, "batch_size", "gas_per_redaction"), "redactions per batch m", "gas per redaction",
             True, True)
        caption(f, run, rows)
        save(f, out, "exp5_gas_consumption.png")
        by_op = defaultdict(list)
        for r in rows:
            if r["system"] == "veredact" and r["gas_used"]:
                by_op[r["op"]].append(num(r["gas_used"]))
        with open(out / "gas_by_operation.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["run", "operation", "transactions", "median_gas", "min_gas", "max_gas"])
            for op, g in sorted(by_op.items()):
                w.writerow([run, op, len(g), statistics.median(g), min(g), max(g)])
    elif rows:
        print("exp5: no receipts (in_process ledger) — no gas figure drawn")


    run, rows = latest(res, "primitives")
    if rows:
        groups = defaultdict(list)
        for r in rows:
            groups[(r["scheme"], r["symbol"], r["instantiation"])].append(num(r["ms"]))
        with open(out / "primitives_table.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["run", "scheme", "symbol", "instantiation", "reps", "median_ms", "mean_ms", "ci95_ms"])
            for (sch, sym, inst), v in groups.items():
                ci = 1.96 * statistics.stdev(v) / len(v) ** 0.5 if len(v) > 1 else 0.0
                w.writerow([run, sch, sym, inst, len(v), f"{statistics.median(v):.4f}", f"{statistics.mean(v):.4f}",
                            f"{ci:.4f}"])
        print(f"primitives: {len(groups)} operations -> {out / 'primitives_table.csv'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "results",
         Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT / "plot")
