"""Issue #7 step 2: layout preview of the redesigned Exp. 3 graph (one panel: end-to-end audit cost).

Drawn ONLY from measured data (release run-2026-11-03, Benchmark/results/), in the paper's figure style. It
previews the layout, not the redesigned result: the 3 Nov run has none of the step-3 changes. Never a paper figure.
  python Other/analysis/exp3_layout_preview.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Benchmark/src"))
import matplotlib.pyplot as plt  # noqa: E402
from veredact_bench.reporting import style  # noqa: E402

RES = ROOT / "Benchmark/results/exp03_audit_efficiency"
OUT = ROOT / "suggest_change/exp3/exp3_layout_preview.png"
SYSTEMS = ["veredact", "veredact-shared-evidence", "veredact-per-record", "S1", "S13"]
RPB = "64"  # veredact.reference_batch


def series(system):
    """(n_Q, service generation + auditor verification) at the drawn records_per_batch."""
    with open(RES / system / "experiment-reps/metrics.json") as f:
        points = json.load(f)["points"]
    out = []
    for k, v in points.items():
        p = dict(x.split("=") for x in k.split("|"))
        if p["records_per_batch"] not in (RPB, "n/a (no batches)"):
            continue
        out.append((int(float(p["n_Q"])), v["retrieval_ms"]["median"] + v["verify_ms"]["median"]))
    return sorted(out)


def main():
    style.apply()
    fig, ax = plt.subplots(figsize=(style.COLUMN_IN, 2.6))
    for s in SYSTEMS:
        pts = series(s)
        style.line(ax, s, [x for x, _ in pts], [y for _, y in pts])
    ax.set(
        xscale="log",
        yscale="log",
        xlabel="Returned records $n_Q$",
        ylabel="Audit cost per query (ms)\nresponse generation + verification",
    )
    ax.set_xticks([10, 100, 1000, 10000], ["10", "100", "1,000", "10,000"])
    ax.minorticks_off()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, frameon=False)
    fig.suptitle(
        "LAYOUT PREVIEW: measured 3 Nov data, none of the step-3 changes - not the redesigned result",
        fontsize=6,
        color="#B60205",
        y=1.0,
    )
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
