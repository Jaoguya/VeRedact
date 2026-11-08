"""Issue #9 step 2: layout preview of the redesigned Exp. 5 graph (one panel: PBN load per redaction).

Drawn ONLY from measured data (release run-2026-11-03, Benchmark/results/), in the paper's figure style:
VeRedact-PQ's anchoring transactions counted from Exp. 1's rounds (two per round: the ABRRR authorization
and the redaction finalization) over the redactions finalized in the same window; each baseline's from its
one ledger write per finalized redaction. Never a paper figure.
  python Other/analysis/exp5_layout_preview.py
"""

import json
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Benchmark/src"))
import matplotlib.pyplot as plt  # noqa: E402
from veredact_bench.reporting import style  # noqa: E402

RES = ROOT / "Benchmark/results/exp01_redaction_throughput"
OUT = ROOT / "suggest_change/exp5/exp5_layout_preview.png"
BASELINES = ["S1", "S13", "S27", "S34"]
ANCHORS_PER_ROUND = 2  # abrrr_authorization (veredact.py:294) + redaction_finalization (veredact.py:400)


def veredact_tx_per_redaction():
    """Rounds and finalized redactions counted in each rate point's measurement window (rows.csv, run 1)."""
    cols = ["sweep", "rate_rps", "in_window", "status", "batch_id"]
    d = pd.read_csv(RES / "veredact/experiment-rep01/rows.csv", usecols=cols, low_memory=False)
    d = d[(d.sweep == "rate") & (d.in_window == 1)]
    out = []
    for rate, g in d.groupby("rate_rps"):
        rounds = g[g.batch_id.notna()].batch_id.nunique()
        out.append((int(rate), ANCHORS_PER_ROUND * rounds / (g.status == "finalized").sum()))
    return sorted(out)


def baseline_tx_per_redaction(system):
    """One ledger write per finalized redaction, in every baseline adapter: the ratio is 1 by construction and
    is drawn from the measurement so the figure shows what was run, not what was assumed."""
    with open(RES / system / "experiment-reps/metrics.json") as f:
        points = json.load(f)["points"]
    out = []
    for k, v in points.items():
        p = dict(x.split("=") for x in k.split("|"))
        if p["sweep"] == "rate" and v.get("throughput_per_s"):
            out.append((int(p["rate_rps"]), 1.0))
    return sorted(out)


def main():
    style.apply()
    fig, ax = plt.subplots(figsize=(style.COLUMN_IN, 2.6))
    series = [("veredact", veredact_tx_per_redaction())]
    series += [(s, baseline_tx_per_redaction(s)) for s in BASELINES]
    for key, pts in series:
        style.line(ax, key, [x for x, _ in pts], [y for _, y in pts])
    ax.set(
        xscale="log",
        yscale="log",
        xlabel="Offered load (req/s)",
        ylabel="PBN anchoring transactions\nper finalized redaction",
    )
    ax.set_xticks([100, 250, 500, 1000, 2000, 5000], ["100", "250", "500", "1,000", "2,000", "5,000"])
    ax.minorticks_off()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3, frameon=False)
    fig.suptitle(
        "LAYOUT PREVIEW: measured 3 Nov data (Exp. 1 rounds and throughput) - not the redesigned result",
        fontsize=6,
        color="#B60205",
        y=1.0,
    )
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
