"""Issue #6 step 2: layout preview of the redesigned Exp. 2 graph (one panel: complete authorization vs n).

Drawn ONLY from measured data (release run-2026-11-03, Benchmark/results/), in the paper's figure style. It
previews the layout, not the redesigned result: the 3 Nov run has no n = 48 or 64 point, and its VeRedact-PQ
numbers still contain the anchoring transaction's build + signing (step 2, fix 3). Never a paper figure.
  python Other/analysis/exp2_layout_preview.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Benchmark/src"))
import matplotlib.pyplot as plt  # noqa: E402
from veredact_bench.reporting import style  # noqa: E402

RES = ROOT / "Benchmark/results/exp02_authorization_latency"
OUT = ROOT / "suggest_change/exp2/exp2_layout_preview.png"
SYSTEMS = ["veredact", "S1", "S34", "S99"]  # Re-ZK dropped from Exp. 2 (author, 7 Nov)
M0 = 64  # the reference round size (Exp. 1 measured median rounds of 53-161 requests)


def series(system):
    """(n, complete authorization per request) at m = M0: Phase 3 + Phase 4 / m, as metrics.json records it."""
    with open(RES / system / "experiment-reps/metrics.json") as f:
        points = json.load(f)["points"]
    out = []
    for k, v in points.items():
        p = dict(x.split("=") for x in k.split("|"))
        if int(float(p["batch_size"])) == M0:
            m = v["auth_complete_per_request_ms"]
            out.append((int(float(p["committee_n"])), m["median"], m.get("ci95_halfwidth") or 0))
    return sorted(out)


def main():
    style.apply()
    fig, ax = plt.subplots(figsize=(style.COLUMN_IN, 2.6))
    for s in SYSTEMS:
        pts = series(s)
        style.line(ax, s, [x for x, _, _ in pts], [y for _, y, _ in pts], yerr=[e for _, _, e in pts])
    ax.set(
        xscale="log",
        yscale="log",
        xlabel="Committee size $n$ ($t=\\lfloor 2n/3\\rfloor+1$)",
        ylabel=f"Authorization per request (ms)\nPhase 3 + Phase 4 / $m$, $m$={M0}",
    )
    ax.set_xticks([4, 7, 10, 16, 32], ["4", "7", "10", "16", "32"])
    ax.minorticks_off()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3, frameon=False)
    fig.suptitle(
        "LAYOUT PREVIEW: measured 3 Nov data (no n = 48/64 point, anchoring still inside Phase 4)"
        "\n- not the redesigned result",
        fontsize=6,
        color="#B60205",
        y=1.02,
    )
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
