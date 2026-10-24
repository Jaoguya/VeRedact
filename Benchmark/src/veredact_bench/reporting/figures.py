"""Paper figures from Benchmark/results/<experiment>/<method>/<tier>/ -> Result/Pdf/<name>.pdf and
Result/Picture/<name>.png.

Names match the manuscript's \\includegraphics (exp1_redaction_throughput, ...). Each figure draws exactly ONE line
per scheme (VeRedact-PQ, Schemes [1], [13], [27], [34], LETA where it runs), never a second setting of a scheme —
Fig. 5 at VeRedact-PQ's default batch (veredact.reference_batch), Fig. 6 normal audit, Fig. 7 the default skew
(workload.zipf_s). Panels follow the captions:
  Fig. 3  (a) throughput, (b) p95 end-to-end latency (s) vs arrival rate, (c) PQCH adaptations (solid) and
          SFMR frontier nodes (dashed, VeRedact-PQ systems) per 1,000 redactions vs Zipf skew
  Fig. 4  Phase 4 authorization (VeRedact-optimize.tex): (a) amortized per request vs selected-set size m,
          (b) one set of m0 vs committee size; schemes without a batch protocol drawn dashed
  Fig. 5  (a) response-generation time, (b) response size vs returned records
  Fig. 6  verification time vs records (normal audit)
  Fig. 7  (a) gas per redaction of every scheme (VeRedact-PQ at m = 1 and at its default batch),
          (b) VeRedact-PQ gas per redaction vs ABRRR batch size, cheapest baseline as a reference line
(2026-10-17, author review: Fig. 3(c) and Fig. 6(b) removed; Fig. 4 counts Phase 3 too; no baseline drawn
against a batch axis it does not have)
No other figure is drawn: only what the manuscript shows (author decision 2026-10-04).
"""

import math
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib import ticker

from veredact_bench import metrics as M
from veredact_bench.reporting import style
from veredact_bench.reporting.load import metrics as _all_metrics
from veredact_bench.reporting.load import num
from veredact_bench.utils.config import RESULT_DIR, load
from veredact_bench.utils.log import get_logger

OUT = RESULT_DIR


def metrics(experiment: str, tier: str) -> dict:
    """metrics.json of the paper's schemes only (style.PAPER_METHODS), in that order."""
    ms = _all_metrics(experiment, tier)
    return {k: ms[k] for k in style.PAPER_METHODS if k in ms}


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
        if xs and len(xs) <= 10 and not getattr(ax, "fixed_xticks", False):  # offset markers set their own
            ax.xaxis.set_minor_locator(ticker.NullLocator())
            ax.set_xticks(xs)
            ax.xaxis.set_major_formatter(plain)
        if ax.get_yscale() == "log":
            lo, hi = ax.get_ylim()
            subs = (1.0,) if hi / lo > 1e3 else (1.0, 2.0, 5.0)  # < 3 decades: 1-2-5 ticks, never an empty axis
            ax.yaxis.set_major_locator(ticker.LogLocator(base=10, subs=subs))
            ax.yaxis.set_minor_formatter(ticker.NullFormatter())
            if getattr(ax, "sci_y", False):  # a x 10^k labels; 1-2-5 ticks when the axis spans few decades
                ax.yaxis.set_major_locator(ticker.LogLocator(base=10, subs=subs))
                ax.yaxis.set_major_formatter(ticker.FuncFormatter(_sci))
            else:
                ax.yaxis.set_major_formatter(plain)


def _sci(v, _=None) -> str:
    """Every major log tick as a x 10^k (10^k when a = 1)."""
    if v <= 0:
        return ""
    k = math.floor(math.log10(v) + 1e-9)
    a = round(v / 10**k, 6)
    return f"$10^{{{k}}}$" if a == 1 else f"${a:g}\\times 10^{{{k}}}$"


def _ci(m: dict, vals: list, *path, scale=1.0):
    """95% CI half-widths across repetitions (aggregated metrics only, scripts/aggregate_reps.py), else None:
    a single run's within-run CI is not an error bar of the plotted median."""
    if not m.get("reps"):
        return None
    out = []
    for v in vals:
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
        out.append((v or 0.0) * scale)
    return out


def _tag(ax, letter):
    ax.set_title(f"({letter})", loc="left")


def _save(fig, name: str, written: list):
    _measured_xticks(fig)
    for ext, sub in (("pdf", "Pdf"), ("png", "Picture")):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        fig.savefig(OUT / sub / f"{name}.{ext}", dpi=300 if ext == "png" else None)
    plt.close(fig)
    written.append(f"Result/Pdf/{name}.pdf")


def _legend(ax, keys=()):
    """Legend of the drawn lines, plus every scheme in keys that has no drawn line (e.g. saturated
    everywhere in Fig. 3), so every scheme of the figure is always listed."""
    handles, labels = ax.get_legend_handles_labels()
    for k in keys:
        if style.label(k) not in labels:
            lab, col, _, mk = style.METHODS[k]
            handles.append(plt.Line2D([], [], color=col, marker=mk, linestyle="-"))
            labels.append(lab)
    if handles:
        order = [style.label(k) for k in style.PAPER_METHODS]
        pairs = sorted(zip(handles, labels), key=lambda p: order.index(p[1]) if p[1] in order else 99)
        ax.legend(*zip(*pairs), frameon=False, ncol=2)


def _saturated(ax, key, xs):
    """Rates where a scheme finalized nothing inside the window: a hollow x on the bottom edge
    (a zero cannot be drawn on a log axis, and silently dropping it would hide the result)."""
    if xs:
        _, col, _, _ = style.METHODS[key]
        f = 1 + 0.06 * (style.PAPER_METHODS.index(key) - 2)  # log-x offset per scheme: coinciding x stay distinct
        ax.plot(
            [x * f for x in xs],
            [0.0] * len(xs),
            transform=ax.get_xaxis_transform(),
            linestyle="none",
            marker="x",
            color=col,
            markersize=6,
            clip_on=False,
            zorder=5,
        )


def fig_exp1(tier, written):
    ms = metrics("exp01_redaction_throughput", tier)
    if not ms:
        return
    want = set(load(tier, "exp01_redaction_throughput")["experiment"]["rates"])  # rows of dropped rates: not drawn
    fig, (a, b, cpanel) = _panels(3, height_in=2.3)
    cf = cpanel.twinx()  # frontier nodes per 1,000 (VeRedact-PQ systems only)
    for key, m in ms.items():
        rate = sorted((k[1], v) for k, v in _points(m).items() if k[0] == "rate" and k[1] in want)
        skew = sorted((k[2], v) for k, v in _points(m).items() if k[0] == "skew")
        ad = [(s, v["pqch_adaptations_per_1000"]) for s, v in skew if v.get("pqch_adaptations_per_1000")]
        if ad:
            style.line(cpanel, key, [s for s, _ in ad], [y for _, y in ad])
        fr = [(s, v.get("frontier_nodes_per_1000")) for s, v in skew if v.get("frontier_nodes_per_1000")]
        if fr and key.startswith("veredact"):
            style.line(cf, key, [s for s, _ in fr], [y for _, y in fr], suffix=" (frontier)", linestyle="--")
        ok = [(x, v) for x, v in rate if v["completed_in_window"]]
        if ok:
            vs = [v for _, v in ok]
            ys = [v["throughput_per_s"] for v in vs]
            style.line(a, key, [x for x, _ in ok], ys, yerr=_ci(m, vs, "throughput_per_s_ci95"))
        _saturated(a, key, [x for x, v in rate if not v["completed_in_window"]])
        # end-to-end p95 in seconds, only where it is a full measurement: a point with more than 5 % of its
        # requests unfinished at the cutoff is a lower bound and is not drawn (author rule: no capped values)
        lat = [(r, v) for r, v in rate if v["latency_ms"].get("n") and not v.get("latency_p95_lower_bound")]
        if lat:
            xs, ys = [r for r, _ in lat], [v["latency_ms"]["p95"] / 1000 for _, v in lat]
            style.line(b, key, xs, ys, yerr=_ci(m, [v for _, v in lat], "latency_ms", "p95_ci95", scale=1e-3))
    rates = sorted(want)
    a.set(xscale="log", yscale="log", xlabel="Arrival rate (req/s)", ylabel="Throughput (redactions/s)")
    b.set(xscale="log", yscale="log", xlabel="Arrival rate (req/s)", ylabel="p95 end-to-end latency (s)")
    for ax in (a, b):  # ticks at the configured rates
        ax.set_xticks(rates)
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.fixed_xticks = True
        ax.sci_y = True  # 10^x labels: one decade per tick, schemes stay apart
    cpanel.set(xlabel="Zipf skew $s$", ylabel="PQCH adaptations / 1,000")
    cf.set_ylabel("Frontier nodes / 1,000")
    cf.grid(False)
    _tag(a, "a")
    _tag(b, "b")
    _tag(cpanel, "c")
    if any(ln.get_marker() == "x" for ln in a.lines):  # explain the x only when one is drawn
        a.set_title(r"$\times$ = nothing finalized during the window", loc="right", fontsize=style.FONT_PT - 1)
    _legend(a, keys=ms)
    _save(fig, "exp1_redaction_throughput", written)


def _flat(ax, key, xs, ys, yerr=None):
    """A scheme without a batch protocol: measured at every x, drawn dashed (its cost does not depend on x)."""
    style.line(ax, key, xs, ys, suffix=" (no batching)", yerr=yerr, linestyle="--")


def fig_exp2(tier, written):
    ms = metrics("exp02_authorization_latency", tier)
    if not ms:
        return
    cfg = load(tier, "exp02_authorization_latency")
    sizes = {k[1] for key, m in ms.items() if key.startswith("veredact") for k in _points(m)}
    n0 = float(cfg["veredact"]["committee_n"])  # per-batch panel: the default batch, or the largest one run
    m0 = (
        float(cfg["veredact"]["reference_batch"])
        if cfg["veredact"]["reference_batch"] in sizes
        else max(sizes, default=1.0)
    )
    fig, (a, b) = _panels(2, height_in=2.2)
    for key, m in ms.items():
        pts = _points(m)
        amort = sorted((k[1], v) for k, v in pts.items() if k[0] == n0)
        per_batch = sorted((k[0], v) for k, v in pts.items() if k[1] == m0)
        batched = any(v["phase4_batch_ms"].get("n") for v in pts.values())
        draw = style.line if batched else _flat
        # VeRedact-optimize.tex Exp. 2: Phase 4 (attestations, freshness, R_e^VR + Gamma_e, committee), amortized
        # over m in (a) and per selected set in (b); a baseline without a batch protocol: m own authorizations
        for ax, series, f in ((a, amort, "auth_per_request_ms"), (b, per_batch, "batch_total_ms")):
            vs = [v for _, v in series]
            draw(ax, key, [x for x, _ in series], [v[f]["median"] for v in vs], yerr=_ci(m, vs, f, "ci95_halfwidth"))
    a.set(xscale="log", yscale="log", xlabel="Selected-set size $m$", ylabel="Authorization\nper request (ms)")
    b.set(
        yscale="log",
        xlabel="Committee size $n$ ($t=\\lfloor 2n/3\\rfloor+1$)",
        ylabel=f"One set of $m$={int(m0)} (ms)",
    )
    for ax in (a, b):
        ax.sci_y = True
    _tag(a, "a")
    _tag(b, "b")
    fig.legend(*a.get_legend_handles_labels(), loc="outside upper center", ncol=2, frameon=False)
    _save(fig, "exp2_authorization_latency", written)


def fig_exp3(tier, written):
    ms = metrics("exp03_audit_efficiency", tier)
    if not ms:
        return
    cfg = load(tier, "exp03_audit_efficiency")
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        by_rpb = defaultdict(list)
        for k, v in _points(m).items():
            if v.get("status") == "ok":
                by_rpb[k[0]].append((k[1], v))
        if not by_rpb:
            continue
        # one line per scheme: VeRedact-PQ at its default batch (or the largest one run); baselines have none
        nums = [r for r in by_rpb if isinstance(r, float)]
        rpb = (
            (
                float(cfg["veredact"]["reference_batch"])
                if float(cfg["veredact"]["reference_batch"]) in nums
                else max(nums)
            )
            if nums
            else next(iter(by_rpb))
        )
        pts = sorted(by_rpb[rpb], key=lambda p: p[0])
        vs = [v for _, v in pts]
        for ax, f in ((a, "retrieval_ms"), (b, "evidence_bytes")):
            ys = [v[f]["median"] for v in vs]
            style.line(ax, key, [x for x, _ in pts], ys, yerr=_ci(m, vs, f, "ci95_halfwidth"))
    a.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Response generation (ms)")
    b.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Response size (bytes)")
    a.sci_y = b.sci_y = True
    _tag(a, "a")
    _tag(b, "b")
    _legend(b)
    _save(fig, "exp3_audit_efficiency", written)


def fig_exp4(tier, written):
    ms = metrics("exp04_verification_time", tier)
    if not ms:
        return
    fig, (a,) = _panels(1, height_in=2.3)
    for key, m in ms.items():
        pts = _points(m)
        xs = sorted(  # normal audit, no injection: one line per scheme
            (k[0], v) for k, v in pts.items() if k[1] == "normal" and k[2] == 0 and v.get("status") == "ok"
        )
        if xs:
            vs = [v for _, v in xs]
            ys = [v["verify_ms"]["median"] for v in vs]
            style.line(a, key, [x for x, _ in xs], ys, yerr=_ci(m, vs, "verify_ms", "ci95_halfwidth"))
    a.set(xscale="log", yscale="log", xlabel="Verified records $n_Q$", ylabel="Verification time (ms)")
    a.sci_y = True
    _legend(a)
    _save(fig, "exp4_verification_time", written)


def fig_exp5(tier, written):
    """(a) gas per finalized redaction of every scheme on the same trace: the baselines send one transaction per
    redaction (their papers define no batching), VeRedact-PQ without batching (m = 1) and at its default ABRRR
    batch (veredact.reference_batch); (b) VeRedact-PQ's own batch-size sensitivity, the cheapest baseline as a
    reference line (a baseline's cost does not depend on m, so it is not drawn against m)."""
    ms = metrics("exp05_gas_consumption", tier)
    if not ms or not any(v["gas_per_redaction"] for m in ms.values() for v in m["points"].values()):
        get_logger().info("exp5: no receipts (in_process ledger) - no gas figure drawn")
        return
    cfg = load(tier, "exp05_gas_consumption")
    s0, m0 = float(cfg["workload"]["zipf_s"]), float(cfg["veredact"]["reference_batch"])
    gas, err = {}, {}  # key -> {m: gas per redaction} at the default skew, and its 95% CI across repetitions
    for key, m in ms.items():
        pts = [(k, v) for k, v in _points(m).items() if k[0] == s0 and v["gas_per_redaction"]]
        gas[key] = {k[1]: v["gas_per_redaction"] for k, v in pts}
        err[key] = {k[1]: (v.get("gas_per_redaction_ci95") or 0.0) if m.get("reps") else 0.0 for k, v in pts}
    fig, (a, b) = _panels(2, height_in=2.1)
    bars = []  # (label, value, colour, hatch, ci)
    for key, g in gas.items():
        if not g:
            continue
        lab, col, _, _ = style.METHODS[key]
        if key.startswith("veredact"):
            for mm, h in ((1.0, "//"), (m0, "")):
                if mm in g:
                    bars.append((f"{lab}\n$m$={int(mm)}", g[mm], col, h, err[key][mm]))
        else:
            mid = sorted(g)[len(g) // 2]  # constant in m (no batching): its value at one measured m
            bars.append((lab, g[mid], col, "", err[key][mid]))
    xs = range(len(bars))
    a.bar(
        xs,
        [b_[1] for b_ in bars],
        yerr=[b_[4] for b_ in bars] if any(b_[4] for b_ in bars) else None,
        color=[b_[2] for b_ in bars],
        hatch=[b_[3] for b_ in bars],
        width=0.6,
        capsize=2,
    )
    a.set_xticks(list(xs), [lab.replace("\n", ", ") for lab, *_ in bars], rotation=30, ha="right")
    a.set(ylabel="Gas per redaction")
    a.fixed_xticks = True
    v = gas.get("veredact", {})
    if v:
        pts = sorted(v.items())
        style.line(b, "veredact", [x for x, _ in pts], [y for _, y in pts], yerr=[err["veredact"][x] for x, _ in pts])
        base = {k: M.median(list(g.values())) for k, g in gas.items() if g and not k.startswith("veredact")}
        if base:
            kmin = min(base, key=base.get)
            _, col, _, _ = style.METHODS[kmin]
            b.axhline(base[kmin], color=col, linestyle="--", label=f"{style.label(kmin)}, one tx per redaction")
        b.set(xscale="log", xlabel="ABRRR batch size $m$", ylabel="Gas per redaction")
        b.set_xticks([x for x, _ in pts])
        b.xaxis.set_minor_locator(ticker.NullLocator())
        b.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:g}"))
        b.fixed_xticks = True  # the reference line's x data are axes coordinates, not batch sizes
        b.legend(frameon=False)
    for ax in (a, b):
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    _tag(a, "a")
    _tag(b, "b")
    _save(fig, "exp5_gas_consumption", written)


def make_all(tier: str) -> list[str]:
    style.apply()
    written: list[str] = []
    for f in (fig_exp1, fig_exp2, fig_exp3, fig_exp4, fig_exp5):
        f(tier, written)
    return written
