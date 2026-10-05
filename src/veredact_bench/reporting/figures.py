"""Paper figures from results/<experiment>/<method>/<tier>/ -> paper/figures/<name>.pdf (+ .png).

Names match the manuscript's \\includegraphics (exp1_redaction_throughput, ...). Each figure draws exactly ONE line
per scheme (VeRedact-PQ and Schemes [1], [13], [27], [34]), never a second setting of a scheme —
Fig. 5 at VeRedact-PQ's default batch (veredact.reference_batch), Fig. 6 normal audit, Fig. 7 the default skew
(workload.zipf_s). Panels follow the captions:
  Fig. 3  (a) throughput, (b) p95 end-to-end latency vs arrival rate, (c) PQCH adaptations per 1,000 vs skew
  Fig. 4  (a) amortized authorization per request vs batch size, (b) per-batch authorization vs committee size
  Fig. 5  (a) response-generation time, (b) response size vs returned records
  Fig. 6  (a) verification time vs records (normal audit), (b) VeRedact-PQ verification-time breakdown
  Fig. 7  (a) total gas per authorization round, (b) amortized gas per redaction vs redactions per batch
No other figure is drawn: only what the manuscript shows (author decision 2026-10-04).
"""

from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib import ticker

from veredact_bench import metrics as M
from veredact_bench.reporting import style
from veredact_bench.reporting.load import metrics as _all_metrics
from veredact_bench.reporting.load import num, rows
from veredact_bench.utils.config import REPO_ROOT, load
from veredact_bench.utils.log import get_logger

OUT = REPO_ROOT / "paper" / "figures"


def metrics(experiment: str, tier: str) -> dict:
    """metrics.json of the paper's five schemes only, in style.PAPER_METHODS order."""
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


def _legend(ax, keys=()):
    """Legend of the drawn lines, plus every scheme in keys that has no drawn line (e.g. saturated
    everywhere in Fig. 3), so all five schemes are always listed."""
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
    fig, (a, b, c) = _panels(3)
    skews = set()
    base_keys = [k for k in ms if not k.startswith("veredact")]
    for key, m in ms.items():
        pts = _points(m)
        rate = sorted((k[1], v) for k, v in pts.items() if k[0] == "rate")
        ok = [(x, v) for x, v in rate if v["completed_in_window"]]
        if ok:
            style.line(a, key, [x for x, _ in ok], [v["throughput_per_s"] for _, v in ok])
            style.line(b, key, [x for x, _ in ok], [v["latency_ms"]["p95"] for _, v in ok])
        zero = [x for x, v in rate if not v["completed_in_window"]]
        _saturated(a, key, zero)
        _saturated(b, key, zero)
        skew = sorted(
            (k[2], v["pqch_adaptations_per_1000"])
            for k, v in pts.items()
            if k[0] == "skew" and v["pqch_adaptations_per_1000"] is not None
        )
        if skew:
            # the baselines all sit at 1,000 (one adaptation per redaction): offset them slightly so none hides
            dx = 0.03 * (base_keys.index(key) - (len(base_keys) - 1) / 2) if key in base_keys else 0.0
            style.line(c, key, [x + dx for x, _ in skew], [y for _, y in skew])
            skews |= {x for x, _ in skew}
    for ax, xl, yl in (
        (a, "Arrival rate (req/s)", "Throughput (red./s)"),
        (b, "Arrival rate (req/s)", "p95 latency (ms)"),
        (c, "Zipf skew $s$", "PQCH adapt. / 1,000"),
    ):
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
    rates = sorted({k[1] for m in ms.values() for k in _points(m) if k[0] == "rate"})
    for ax in (a, b):  # ticks at the measured rates, not at the offset x markers
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks(rates)
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    c.set_xticks(sorted(skews))
    for ax in (a, b, c):
        ax.fixed_xticks = True
    c.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    for ax, t in zip((a, b, c), "abc"):
        _tag(ax, t)
    if any(ln.get_marker() == "x" for ln in a.lines):  # explain the x only when one is drawn
        a.set_title(r"$\times$ = nothing finalized during the window", loc="right", fontsize=style.FONT_PT - 1)
    _legend(a, keys=ms)
    _save(fig, "exp1_redaction_throughput", written)


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
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        pts = _points(m)
        amort = sorted((k[1], v["auth_per_request_ms"]["median"]) for k, v in pts.items() if k[0] == n0)
        style.line(a, key, [x for x, _ in amort], [y for _, y in amort])
        if key.startswith("veredact"):  # one ABRRR batch of m0 requests: Phase 4 time
            per_batch = sorted((k[0], v["phase4_batch_ms"]["median"]) for k, v in pts.items() if k[1] == m0)
        else:
            # baselines: m0 of their own authorizations, measured as one batch (exp02 batch_total_ms)
            per_batch = sorted((k[0], v["batch_total_ms"]["median"]) for k, v in pts.items() if k[1] == m0)
        style.line(b, key, [x for x, _ in per_batch], [y for _, y in per_batch])
    a.set(xscale="log", yscale="log", xlabel="Batch size $m$", ylabel="Amortized per request (ms)")
    b.set(
        yscale="log",
        xlabel="Committee size $n$ ($t=\\lfloor 2n/3\\rfloor+1$)",
        ylabel="Per batch (ms)",
        title=f"one batch of $m$={int(m0)} requests",
    )
    _tag(a, "a")
    _tag(b, "b")
    _legend(a)
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
        style.line(a, key, [x for x, _ in pts], [v["retrieval_ms"]["median"] for _, v in pts])
        style.line(b, key, [x for x, _ in pts], [v["evidence_bytes"]["median"] for _, v in pts])
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
)


def fig_exp4(tier, written):
    ms = metrics("exp04_verification_time", tier)
    if not ms:
        return
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        pts = _points(m)
        xs = sorted(  # normal audit only: one line per scheme
            (k[0], v["verify_ms"]["median"])
            for k, v in pts.items()
            if k[1] == "normal" and k[2] == 0 and v.get("status") == "ok"
        )
        if xs:
            style.line(a, key, [x for x, _ in xs], [y for _, y in xs])
    a.set(xscale="log", yscale="log", xlabel="Verified records $n_Q$", ylabel="Verification time (ms)")
    vr = [
        r
        for r in rows("exp04_verification_time", tier)
        if r["system"] == "veredact"
        and r.get("status") == "ok"
        and num(r["inject_fraction"]) == 0
        and r["level"] == "normal"
    ]
    if vr:
        n_max = max(int(r["n_Q"]) for r in vr)
        levels = ["normal"]
        bottom = [0.0] * len(levels)
        for col, name in BREAKDOWN:
            h = [
                M.median([num(r[f"verify_{col}"]) for r in vr if r["level"] == lv and int(r["n_Q"]) == n_max])
                for lv in levels
            ]
            b.bar(levels, h, bottom=bottom, label=name, width=0.5)
            bottom = [x + y for x, y in zip(bottom, h)]
        b.set(ylabel="Verification time (ms)", title=f"VeRedact-PQ normal audit, $n_Q$ = {n_max}")
        b.legend(
            frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12)
        )  # below: no swatch on its own colour
    _tag(a, "a")
    _tag(b, "b")
    _legend(a)
    _save(fig, "exp4_verification_time", written)


def fig_exp5(tier, written):
    ms = metrics("exp05_gas_consumption", tier)
    if not ms or not any(v["gas_per_redaction"] for m in ms.values() for v in m["points"].values()):
        get_logger().info("exp5: no receipts (in_process ledger) - no gas figure drawn")
        return
    s0 = float(load(tier, "exp05_gas_consumption")["workload"]["zipf_s"])  # one line per scheme: default skew
    fig, (a, b) = _panels(2)
    for key, m in ms.items():
        by_s = defaultdict(list)
        for k, v in _points(m).items():
            if v["gas_per_redaction"]:
                by_s[k[0]].append((k[1], v))
        if not by_s:
            continue
        s = s0 if s0 in by_s else max(by_s)
        pts = sorted(by_s[s], key=lambda p: p[0])
        style.line(a, key, [x for x, _ in pts], [v["gas_per_redaction"] * x for x, v in pts])
        style.line(b, key, [x for x, _ in pts], [v["gas_per_redaction"] for _, v in pts])
    a.set(xscale="log", yscale="log", xlabel="Redactions per batch $m$", ylabel="Total gas per round")
    b.set(
        xscale="log",
        yscale="log",
        xlabel="Redactions per batch $m$",
        ylabel="Gas per redaction",
        title=f"Zipf skew $s$ = {s0:g}",
    )
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
