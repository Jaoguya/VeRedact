"""Issue #5 step 2: layout preview of the redesigned Exp. 1 graph (one panel: throughput vs offered load).

Drawn ONLY from measured data (release run-2026-11-03, Benchmark/results/), in the paper's figure style, over the
redesign's rate range (<= 1,000 req/s). It previews the layout, not the redesigned result: the 3 Nov run had no
invalid requests and no FreshLeaf. Never a paper figure.
  python Other/analysis/exp1_layout_preview.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Benchmark/src"))
import matplotlib.pyplot as plt
from veredact_bench.reporting import style

RES = ROOT / "Benchmark/results/exp01_redaction_throughput"
OUT = ROOT / "suggest_change/exp1/exp1_layout_preview.png"
SYSTEMS = ["veredact", "veredact-fixed-batch", "veredact-cora-no-sfmr", "veredact-per-request", "S1", "S13", "S27", "S34"]
MAX_RATE = 1000  # redesign range: 25-1,000 req/s (3 Nov has 100, 250, 500, 1,000)


def rate_points(system):
    with open(RES / system / "experiment-reps/metrics.json") as f:
        points = json.load(f)["points"]
    out = []
    for k, v in points.items():
        p = dict(x.split("=") for x in k.split("|"))
        if p["sweep"] == "rate" and int(p["rate_rps"]) <= MAX_RATE:
            out.append((int(p["rate_rps"]), v["throughput_per_s"], v.get("throughput_per_s_ci95") or 0))
    return sorted(out)


def main():
    style.apply()
    fig, ax = plt.subplots(figsize=(style.COLUMN_IN, 2.6))
    for s in SYSTEMS:
        pts = rate_points(s)
        style.line(ax, s, [x for x, _, _ in pts], [y for _, y, _ in pts], yerr=[e for _, _, e in pts])
    ax.set(xscale="log", yscale="log", xlabel="Offered load (req/s)", ylabel="Finalized valid redactions/s")
    ax.set_xticks([100, 250, 500, 1000], ["100", "250", "500", "1,000"])
    ax.minorticks_off()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3, frameon=False)
    fig.suptitle(
        "LAYOUT PREVIEW: measured 3 Nov data (0 % invalid, no FreshLeaf) - not the redesigned result",
        fontsize=6,
        color="#B60205",
        y=1.0,
    )
    fig.savefig(OUT, dpi=200)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
