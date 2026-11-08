"""Paper figures from Benchmark/results/<experiment>/<method>/<tier>/ -> Result/Pdf/<name>.pdf and
Result/Picture/<name>.png.

Names match the manuscript's includegraphics (exp1_redaction_throughput, ...); Overleaf/VeRedact-optimize.tex.
Each figure draws one line per system: VeRedact-PQ, its internal ablation variants (in VeRedact-PQ's colour),
Schemes [1], [13], [27], [34] and LETA where they run. Fig. 5 at VeRedact-PQ's default sharing level
(veredact.reference_batch records per authorization batch). Panels follow the captions:
  Fig. 3  one panel (#5): finalized valid redactions/s vs arrival rate, 20 % invalid (stale, absent) requests
  Fig. 4  one panel (#6): complete authorization per request vs committee size n at m = reference_batch;
          schemes without a batch protocol drawn dashed
  Fig. 5  one panel (#7): end-to-end audit cost per query (generation + verification) vs returned records
  Fig. 6  (a) verification vs PQZK escalation fraction, (b) breakdown, (c) rejection / acceptance per fault class
  Fig. 7  (a) finalization / RAI-checkpoint transaction size, (b) finalization latency per validator count,
          both vs affected batches |Omega_e| (VeRedact-optimize.tex: no gas)
No other figure is drawn: only what the manuscript shows.
"""

import math
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib import ticker

from veredact_bench.reporting import style
from veredact_bench.reporting.load import metrics as _all_metrics
from veredact_bench.reporting.load import num
from veredact_bench.utils.config import RESULT_DIR, load

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


def _legend(ax, keys=(), outside=False):
    """Legend of the drawn lines, plus every scheme in keys that has no drawn line (e.g. saturated
    everywhere in Fig. 3), so every scheme of the figure is always listed. outside: above the panels (many
    systems, e.g. Fig. 3 with the ablation variants)."""
    handles, labels = ax.get_legend_handles_labels()
    for k in keys:
        if style.label(k) not in labels:
            lab, col, ls, mk = style.METHODS[k]
            handles.append(plt.Line2D([], [], color=col, marker=mk, linestyle=ls))
            labels.append(lab)
    if handles:
        order = [style.label(k) for k in style.PAPER_METHODS]
        pairs = sorted(zip(handles, labels), key=lambda p: order.index(p[1]) if p[1] in order else 99)
        if outside:
            ax.figure.legend(*zip(*pairs), loc="outside upper center", ncol=3, frameon=False)
        else:
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
    """One panel (#5 redesign): finalized VALID redactions/s vs offered load, one line per system, on the 20 %
    invalid workload. p95 latency, accepted invalid requests and the skew sweep (PQCH adaptations, frontier per
    1,000) are in metrics.json and go to the text, not to panels."""
    ms = metrics("exp01_redaction_throughput", tier)
    if not ms:
        return
    want = set(load(tier, "exp01_redaction_throughput")["experiment"]["rates"])  # rows of dropped rates: not drawn
    fig, (a,) = _panels(1, height_in=2.6)
    for key, m in ms.items():
        rate = sorted((k[1], v) for k, v in _points(m).items() if k[0] == "rate" and k[1] in want)
        ok = [(x, v) for x, v in rate if v["completed_in_window"]]
        if ok:
            vs = [v for _, v in ok]
            ys = [v["throughput_per_s"] for v in vs]
            style.line(a, key, [x for x, _ in ok], ys, yerr=_ci(m, vs, "throughput_per_s_ci95"))
        _saturated(a, key, [x for x, v in rate if not v["completed_in_window"]])
    a.set(xscale="log", yscale="log", xlabel="Arrival rate (req/s)", ylabel="Valid redactions\nfinalized per second")
    a.set_xticks(sorted(want))  # ticks at the configured rates
    a.xaxis.set_minor_locator(ticker.NullLocator())
    a.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    a.fixed_xticks = True
    a.sci_y = True  # 10^x labels: one decade per tick, schemes stay apart
    if any(ln.get_marker() == "x" for ln in a.lines):  # explain the x only when one is drawn
        a.set_title(r"$\times$ = nothing finalized during the window", loc="right", fontsize=style.FONT_PT - 1)
    _legend(a, keys=ms, outside=True)
    _save(fig, "exp1_redaction_throughput", written)


def _flat(ax, key, xs, ys, yerr=None):
    """A scheme without a batch protocol: measured at every x, drawn dashed (its cost does not depend on x)."""
    style.line(ax, key, xs, ys, suffix=" (no batching)", yerr=yerr, linestyle="--")


def fig_exp2(tier, written):
    """One panel (#6 redesign): COMPLETE authorization per request (Phase 3 validation + Phase 4 / m; a baseline's
    whole authorization) vs committee size n, at the reference round m = veredact.reference_batch (or the largest
    m run). The m axis is a table in the text (metrics.json, every m at every n)."""
    ms = metrics("exp02_authorization_latency", tier)
    if not ms:
        return
    cfg = load(tier, "exp02_authorization_latency")
    sizes = {k[1] for m in ms.values() for k in _points(m)}
    m0 = (
        float(cfg["veredact"]["reference_batch"])
        if cfg["veredact"]["reference_batch"] in sizes
        else max(sizes, default=1.0)
    )
    fig, (a,) = _panels(1, height_in=2.6)
    f = "auth_complete_per_request_ms"
    for key, m in ms.items():
        pts = _points(m)
        series = sorted((k[0], v) for k, v in pts.items() if k[1] == m0 and v.get(f, {}).get("n"))
        if not series:
            continue
        batched = any(v.get("phase4_batch_ms", {}).get("n") for v in pts.values())
        draw = style.line if batched else _flat  # no batch protocol: m own authorizations, drawn dashed
        vs = [v for _, v in series]
        draw(a, key, [x for x, _ in series], [v[f]["median"] for v in vs], yerr=_ci(m, vs, f, "ci95_halfwidth"))
    a.set(
        xscale="log",
        yscale="log",
        xlabel="Committee size $n$ ($t=\\lfloor 2n/3\\rfloor+1$)",
        ylabel=f"Authorization per request\n(ms, $m$={int(m0)})",
    )
    a.sci_y = True
    _legend(a, outside=True)
    _save(fig, "exp2_authorization_latency", written)


def fig_exp3(tier, written):
    ms = metrics("exp03_audit_efficiency", tier)
    if not ms:
        return
    cfg = load(tier, "exp03_audit_efficiency")
    fig, (a,) = _panels(1, height_in=2.6)
    for key, m in ms.items():
        by_rpb = defaultdict(list)
        for k, v in _points(m).items():
            if v.get("status") == "ok":
                by_rpb[k[0]].append((k[1], v))
        if not by_rpb:
            continue
        # one line per system: VeRedact-PQ systems at the default sharing level (or the largest one run)
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
        f = "end_to_end_ms"  # #7: generation + verification per query; each term and the size go to the text
        ok = [(x, v) for x, v in pts if v.get(f, {}).get("n")]
        if ok:
            ys = [v[f]["median"] for _, v in ok]
            style.line(a, key, [x for x, _ in ok], ys, yerr=_ci(m, [v for _, v in ok], f, "ci95_halfwidth"))
    a.set(
        xscale="log",
        yscale="log",
        xlabel="Returned records $n_Q$",
        ylabel="Audit cost per query (ms)\n(generation + verification)",
    )
    a.sci_y = True
    _legend(a, outside=True)
    _save(fig, "exp3_audit_efficiency", written)


def fig_exp4(tier, written):
    """One panel (#8): auditor verification time vs returned records n_Q. VeRedact-PQ routine (d_Q = 0) and deep
    (every request escalated to PQZK, the largest d_Q/n_Q run); Scheme [1] per record; Scheme [13] with one
    decision per query (its Audit) and per block (its Query phase, S13-per-block). The breakdown, the
    intermediate escalation fractions and the fault classes go to the text (tables), not to panels."""
    ms = metrics("exp04_verification_time", tier)
    if not ms:
        return
    fig, (a,) = _panels(1, height_in=2.4)
    for key, m in ms.items():
        pts = {k: v for k, v in _points(m).items() if v.get("status") == "ok" and k[2] == "none"}
        levels = sorted({k[1] for k in pts})
        for d in [levels[0], levels[-1]] if len(levels) > 1 else levels:
            ok = sorted((k[0], v) for k, v in pts.items() if k[1] == d and (v.get("verify_ms") or {}).get("n"))
            if not ok:
                continue
            deep = d > 0
            suffix = ", deep" if deep else (", whole query" if key == "S13" else "")
            style.line(
                a,
                key,
                [n for n, _ in ok],
                [v["verify_ms"]["median"] for _, v in ok],
                suffix=suffix,
                yerr=_ci(m, [v for _, v in ok], "verify_ms", "ci95_halfwidth"),
                linestyle="--" if deep else None,
            )
    a.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Auditor verification (ms)")
    a.sci_y = True
    _legend(a, outside=True)
    _save(fig, "exp4_verification_time", written)


def fig_exp5(tier, written):
    """(a) size of the redaction-finalization transaction (Phase 5) and of the RAI-checkpoint transaction (Phase 6,
    dashed) vs |Omega_e| at the default validator count; (b) submission -> QBFT finalization latency of the
    finalization transaction vs |Omega_e|, one line per validator count."""
    ms = metrics("exp05_blockchain_overhead", tier)
    if "veredact" not in ms:
        return
    v0 = float(load(tier, "exp05_blockchain_overhead")["ledger"]["validators"])
    pts = _points(ms["veredact"])
    fig, (a, b) = _panels(2, height_in=2.1)
    _, col, _, mk = style.METHODS["veredact"]
    base = sorted((k[1], v) for k, v in pts.items() if k[0] == v0)
    for f, ls, lab in (("finalize_tx_bytes", "-", "redaction finalization"), ("rai_tx_bytes", "--", "RAI checkpoint")):
        series = [(x, v[f]["median"] / 1024) for x, v in base if v[f].get("n")]
        if series:
            a.plot(*zip(*series), color=col, linestyle=ls, marker=mk, label=lab)
    shades = ("#56B4E9", "#0072B2", "#003F63", "#000000")
    for i, n in enumerate(sorted({k[0] for k in pts})):
        series = [(k[1], v["finalize_ms"]["median"] / 1000) for k, v in sorted(pts.items()) if k[0] == n]
        b.plot(*zip(*series), color=shades[i % len(shades)], marker=mk, label=f"{int(n)} validators")
    a.set(xscale="log", xlabel="Affected batches $|\\Omega_e|$", ylabel="Transaction size (KiB)")
    b.set(xscale="log", xlabel="Affected batches $|\\Omega_e|$", ylabel="Finalization latency (s)")
    _tag(a, "a")
    _tag(b, "b")
    a.legend(frameon=False)
    b.legend(frameon=False)
    _save(fig, "exp5_blockchain_overhead", written)


def make_all(tier: str) -> list[str]:
    style.apply()
    written: list[str] = []
    for f in (fig_exp1, fig_exp2, fig_exp3, fig_exp4, fig_exp5):
        f(tier, written)
    return written
