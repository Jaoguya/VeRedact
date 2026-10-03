"""Paper figures from results/<experiment>/<method>/<tier>/ -> paper/figures/<name>.pdf (+ .png).

Names match the manuscript's \\includegraphics (exp1_redaction_throughput, ...). Panels follow the captions:
  Fig. 3  (a) throughput, (b) p95 end-to-end latency vs arrival rate, (c) PQCH adaptations per 1,000 vs skew
  Fig. 4  (a) amortized authorization per request vs batch size, (b) per-batch authorization vs committee size
  Fig. 5  (a) response-generation time, (b) response size vs returned records
  Fig. 6  (a) verification time vs records (normal, deep), (b) VeRedact-PQ verification-time breakdown
  Fig. 7  (a) total gas per authorization round, (b) amortized gas per redaction vs redactions per batch
plus exp4_granularity (valid records falsely rejected vs injected fraction; Exp. 4 text).
"""

from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib import ticker

from veredact_bench import metrics as M
from veredact_bench.reporting import style
from veredact_bench.reporting.load import metrics, num, rows
from veredact_bench.utils.config import REPO_ROOT, load
from veredact_bench.utils.log import get_logger

OUT = REPO_ROOT / "paper" / "figures"


def _points(m: dict) -> dict:
    """metrics.json points -> {(axis values...): stats} with numeric axis values where possible."""
    out = {}
    for k, v in m["points"].items():
        out[
            tuple(
                num(p.split("=", 1)[1]) if num(p.split("=", 1)[1]) is not None else p.split("=", 1)[1]
                for p in k.split("|")
            )
        ] = v
    return out


def _panels(n: int, height_in: float = 1.9):
    fig, axes = plt.subplots(n, 1, figsize=(style.COLUMN_IN, height_in * n), layout="constrained")
    return fig, list(axes) if n > 1 else [axes]


def _measured_xticks(fig):
    """Ticks only at the x values that were measured, labelled as plain numbers (no 10^x minor clutter)."""
    plain = ticker.FuncFormatter(lambda v, _: f"{v:g}")
    for ax in fig.axes:
        xs = sorted({x for ln in ax.lines for x in ln.get_xdata()})
        if xs and len(xs) <= 10:
            ax.xaxis.set_minor_locator(ticker.NullLocator())
            ax.set_xticks(xs)
            ax.xaxis.set_major_formatter(plain)
        if ax.get_yscale() == "log":
            ax.yaxis.set_minor_formatter(ticker.NullFormatter())
            ax.yaxis.set_major_formatter(plain)


def _tag(ax, letter):
    ax.set_title(f"({letter})", loc="left")


def _save(fig, name: str, written: list):
    _measured_xticks(fig)
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300 if ext == "png" else None)
    plt.close(fig)
    written.append(f"paper/figures/{name}.pdf")


def _legend(ax):
    if ax.get_legend_handles_labels()[0]:
        ax.legend(frameon=False, ncol=2)


def fig_exp1(tier, written):
    ms = metrics("exp01_redaction_throughput", tier)
    if not ms:
        return
    fig, (a, b, c) = _panels(3)
    for key, m in ms.items():
        pts = _points(m)
        rate = sorted((k[1], v) for k, v in pts.items() if k[0] == "rate" and v["finalized"])
        if rate:
            style.line(a, key, [x for x, _ in rate], [v["throughput_per_s"] for _, v in rate])
            style.line(b, key, [x for x, _ in rate], [v["latency_ms"]["p95"] for _, v in rate])
        skew = sorted(
            (k[2], v["pqch_adaptations_per_1000"])
            for k, v in pts.items()
            if k[0] == "skew" and v["pqch_adaptations_per_1000"] is not None
        )
        if skew:
            style.line(c, key, [x for x, _ in skew], [y for _, y in skew])
    for ax, xl, yl in (
        (a, "Arrival rate (req/s)", "Throughput (red./s)"),
        (b, "Arrival rate (req/s)", "p95 latency (ms)"),
        (c, "Zipf skew $s$", "PQCH adapt. / 1,000"),
    ):
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
    for ax in (a, b):
        ax.set_xscale("log")
        ax.set_yscale("log")
    for ax, t in zip((a, b, c), "abc"):
        _tag(ax, t)
    _legend(a)
    _save(fig, "exp1_redaction_throughput", written)


def fig_exp2(tier, written):
    ms = metrics("exp02_authorization_latency", tier)
    if not ms:
        return
    cfg = load(tier, "exp02_authorization_latency")
    sizes = {k[1] for key, m in ms.items() if key.startswith("veredact") for k in _points(m)}
    n0 = float(cfg["veredact"]["committee_n"])  # per-batch panel: the default batch, or the largest one run
    m0 = float(cfg["veredact"]["fixed_batch"]) if cfg["veredact"]["fixed_batch"] in sizes else max(sizes, default=1.0)
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        pts = _points(m)
        amort = sorted((k[1], v["auth_per_request_ms"]["median"]) for k, v in pts.items() if k[0] == n0)
        style.line(a, key, [x for x, _ in amort], [y for _, y in amort])
        if key.startswith("veredact"):  # one ABRRR batch of m0 requests: Phase 4 time
            per_batch = sorted((k[0], v["phase4_batch_ms"]["median"]) for k, v in pts.items() if k[1] == m0)
        else:  # baselines authorize one request per batch
            per_batch = sorted((k[0], v["auth_per_request_ms"]["median"]) for k, v in pts.items() if k[1] == 1)
        style.line(b, key, [x for x, _ in per_batch], [y for _, y in per_batch])
    a.set(xscale="log", yscale="log", xlabel="Batch size $m$", ylabel="Amortized per request (ms)")
    b.set(
        yscale="log",
        xlabel="Committee size $n$ ($t=\\lfloor 2n/3\\rfloor+1$)",
        ylabel="Per batch (ms)",
        title=f"VeRedact-PQ: one batch of $m$={int(m0)}",
    )
    _tag(a, "a")
    _tag(b, "b")
    _legend(a)
    _save(fig, "exp2_authorization_latency", written)


_RPB_STYLE = {1: "-", 4: "--", 8: "--", 16: "-.", 64: ":"}


def fig_exp3(tier, written):
    ms = metrics("exp03_audit_efficiency", tier)
    if not ms:
        return
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        by_rpb = defaultdict(list)
        for k, v in _points(m).items():
            if v.get("status") == "ok":
                by_rpb[k[0]].append((k[1], v))
        for rpb, pts in sorted(by_rpb.items(), key=lambda kv: str(kv[0])):
            pts.sort(key=lambda p: p[0])
            suffix = f" ($m$={int(rpb)})" if isinstance(rpb, float) else ""
            style.line(a, key, [x for x, _ in pts], [v["retrieval_ms"]["median"] for _, v in pts], suffix)
            style.line(b, key, [x for x, _ in pts], [v["evidence_bytes"]["median"] for _, v in pts], suffix)
            if isinstance(rpb, float):
                for ax in (a, b):
                    ax.lines[-1].set_linestyle(_RPB_STYLE.get(int(rpb), "-"))
    a.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Response generation (ms)")
    b.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Response size (bytes)")
    _tag(a, "a")
    _tag(b, "b")
    _legend(b)
    _save(fig, "exp3_audit_efficiency", written)


BREAKDOWN = (
    ("response_ms", "Response + query"),
    ("rai_mp_ms", "RAI multiproof"),
    ("committee_ms", "Committee approvals"),
    ("attest_ms", "Attestations"),
    ("state_ms", "State + PQCH"),
    ("zk_ms", "PQZK"),
)


def fig_exp4(tier, written):
    ms = metrics("exp04_verification_time", tier)
    if not ms:
        return
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        pts = _points(m)
        for level in ("normal", "deep"):
            xs = sorted(
                (k[0], v["verify_ms"]["median"])
                for k, v in pts.items()
                if k[1] == level and k[2] == 0 and v.get("status") == "ok"
            )
            if xs and (level == "normal" or key.startswith("veredact")):
                style.line(a, key, [x for x, _ in xs], [y for _, y in xs], f" ({level})")
                if level == "deep":
                    a.lines[-1].set_linestyle("--")
    a.set(xscale="log", yscale="log", xlabel="Verified records $n_Q$", ylabel="Verification time (ms)")
    vr = [
        r
        for r in rows("exp04_verification_time", tier)
        if r["system"] == "veredact" and r.get("status") == "ok" and num(r["inject_fraction"]) == 0
    ]
    if vr:
        n_max = max(int(r["n_Q"]) for r in vr)
        levels = [lv for lv in ("normal", "deep") if any(r["level"] == lv for r in vr)]
        bottom = [0.0] * len(levels)
        for col, name in BREAKDOWN:
            h = [
                M.median([num(r[f"verify_{col}"]) for r in vr if r["level"] == lv and int(r["n_Q"]) == n_max])
                for lv in levels
            ]
            b.bar(levels, h, bottom=bottom, label=name, width=0.5)
            bottom = [x + y for x, y in zip(bottom, h)]
        b.set(ylabel="Verification time (ms)", title=f"VeRedact-PQ, $n_Q$ = {n_max}")
        b.legend(frameon=False, ncol=2)
    _tag(a, "a")
    _tag(b, "b")
    _legend(a)
    _save(fig, "exp4_verification_time", written)
    fig, (g,) = _panels(1)
    for key, m in ms.items():
        pts = defaultdict(list)
        for k, v in _points(m).items():
            if v.get("status") == "ok":
                pts[k[2]].append(v["false_rejection_rate"])
        xs = sorted(pts)
        style.line(g, key, xs, [M.mean(pts[x]) for x in xs])
    g.set(xlabel="Injected fraction", ylabel="Valid records falsely rejected")
    _legend(g)
    _save(fig, "exp4_granularity", written)


def fig_exp5(tier, written):
    ms = metrics("exp05_gas_consumption", tier)
    if not ms or not any(v["gas_per_redaction"] for m in ms.values() for v in m["points"].values()):
        get_logger().info("exp5: no receipts (in_process ledger) - no gas figure drawn")
        return
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        by_s = defaultdict(list)
        for k, v in _points(m).items():
            if v["gas_per_redaction"]:
                by_s[k[0]].append((k[1], v))
        for s, pts in sorted(by_s.items()):
            pts.sort(key=lambda p: p[0])
            style.line(a, key, [x for x, _ in pts], [v["gas_per_redaction"] * x for x, v in pts], f" $s$={s}")
            style.line(b, key, [x for x, _ in pts], [v["gas_per_redaction"] for _, v in pts], f" $s$={s}")
            if s:
                for ax in (a, b):
                    ax.lines[-1].set_linestyle("--")
    a.set(xscale="log", yscale="log", xlabel="Redactions per batch $m$", ylabel="Total gas per round")
    b.set(xscale="log", yscale="log", xlabel="Redactions per batch $m$", ylabel="Gas per redaction")
    _tag(a, "a")
    _tag(b, "b")
    _legend(b)
    _save(fig, "exp5_gas_consumption", written)


def make_all(tier: str) -> list[str]:
    style.apply()
    written: list[str] = []
    for f in (fig_exp1, fig_exp2, fig_exp3, fig_exp4, fig_exp5):
        f(tier, written)
    return written
