"""Issue #8: layout preview of the redesigned Exp. 4 figure. A PREVIEW, never a paper figure.

Left: today's Fig. 6 (three panels, Result/Picture/exp4_verification_time.png as committed).
Right: the redesigned single panel. Every solid/dashed line is a measured median from release run-2026-11-03
(experiment-reps/metrics.json). "Scheme [13], per block" is NOT measured yet: it is drawn hollow and dotted as a
PREDICTION (lower bound) = distinct blocks of the first n_Q redactions x (T_Tag verify + T_CV^c) from Exp. 0
(non-membership check left out, so the real line can only be higher). Distinct blocks are read off S13's own
measured response generation (one Alg. 1 witness per block, ~equal cost): retrieval(n_Q) / (retrieval(10^4) / 391);
all 391 blocks are hit at n_Q = 10^4 (a Zipf 0.8 estimate gives 9.4 / 69 / 286 / 391).
  python Other/analysis/exp4_preview.py   ->  suggest_change/exp4/exp4_layout_preview.png
"""

import json
import pathlib
import sys

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Benchmark/src"))
from veredact_bench.reporting import style  # noqa: E402

RES = ROOT / "Benchmark/results"
OUT = ROOT / "suggest_change/exp4/exp4_layout_preview.png"


def points(exp, system):
    with open(RES / exp / system / "experiment-reps/metrics.json") as f:
        for k, v in json.load(f)["points"].items():
            yield dict(x.split("=", 1) for x in k.split("|")), v


def measured(system, deep):
    """[(n_Q, median ms, ci95 half-width)] of the fault-free points at escalation fraction `deep`."""
    out = [
        (int(p["n_Q"]), v["verify_ms"]["median"], v["verify_ms"]["ci95_halfwidth"])
        for p, v in points("exp04_verification_time", system)
        if p["fault_kind"] == "none" and float(p["deep_fraction"]) == deep
    ]
    return sorted(out)


def s13_per_block_prediction(n_axis):
    prim = {p["instantiation"]: v["median"] for p, v in points("exp00_primitives", "S13")}
    tag = prim["identity-based tag verification, RSA-3072 [13]"]
    per_block = tag + prim["double-trapdoor CH verify, RSA-3072 [13]"]
    d = pd.read_csv(
        RES / "exp04_verification_time/S13/experiment-rep01/rows.csv",
        usecols=["n_Q", "fault_kind", "retrieval_ms"],
        low_memory=False,
    )
    gen = d[d.fault_kind == "none"].groupby("n_Q").retrieval_ms.median()
    per_witness = gen[10000] / 391
    blocks = {n: float(gen[n] / per_witness) for n in n_axis}
    return [(n, blocks[n] * per_block, blocks[n]) for n in n_axis], per_block


def main():
    style.apply()
    fig = plt.figure(figsize=(7.4, 3.9), layout="constrained")
    left, right = fig.subfigures(1, 2, width_ratios=[0.8, 1.2])

    ax0 = left.subplots()
    ax0.imshow(mpimg.imread(ROOT / "Result/Picture/exp4_verification_time.png"))
    ax0.axis("off")
    ax0.set_title("Now: Fig. 6, three panels (3 Nov run)", fontsize=8)

    ax = right.subplots()
    for key, deep, suffix, ls in (
        ("S1", 0.0, "", None),
        ("veredact", 1.0, ", deep (all PQZK proofs)", "--"),
        ("veredact", 0.0, ", routine", None),
        ("S13", 0.0, ", whole query (Audit)", None),
    ):
        pts = measured(key, deep)
        style.line(
            ax,
            key,
            [n for n, _, _ in pts],
            [m for _, m, _ in pts],
            suffix=suffix,
            yerr=[c for _, _, c in pts],
            linestyle=ls,
        )
    pred, per_block = s13_per_block_prediction([10, 100, 1000, 10000])
    ax.plot(
        [n for n, _, _ in pred],
        [m for _, m, _ in pred],
        linestyle=":",
        marker="D",
        markerfacecolor="white",
        color=style.METHODS["S13"][1],
        label="Scheme [13], per block (Query)\nPREDICTION, lower bound",
    )
    for n, m, b in pred:
        off = (-46, 6) if n == 10000 else (5, -9)
        ax.annotate(
            f"{b:.0f} blocks", (n, m), textcoords="offset points", xytext=off, fontsize=6, color=style.METHODS["S13"][1]
        )
    ax.set(xscale="log", yscale="log", xlabel="Returned records $n_Q$", ylabel="Auditor verification (ms)")
    ax.set_xticks([10, 100, 1000, 10000], ["10", "100", "1000", "10000"])
    ax.minorticks_off()
    ax.set_title("Redesign: one panel (expected)", fontsize=8)
    ax.legend(frameon=False, fontsize=6, loc="upper left")
    ax.text(
        0.99,
        0.30,
        "PREVIEW, not a paper figure.\nSolid/dashed: measured 3 Nov medians\n(95% CI over 3 runs).\n"
        f"Dotted: prediction = blocks x {per_block:.1f} ms\n(Exp. 0), lower bound.",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.5,
        color="#555555",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=250)
    print(OUT, {n: round(m) for n, m, _ in pred})


if __name__ == "__main__":
    main()
