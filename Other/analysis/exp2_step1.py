"""Issue #6 step 1: why VeRedact-PQ loses in Exp. 2. Diagnostic only, never a paper number.

Reads release run-2026-11-03 unpacked into Benchmark/results/ and prints the tables the verdict cites:
  python Other/analysis/exp2_step1.py
"""

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Benchmark/results"
RES = ROOT / "exp02_authorization_latency"
SYSTEMS = ["veredact", "veredact-re-zk", "S1", "S34", "S99"]
N0 = 7  # configs/methods/veredact.yaml committee_n (panel (a) is drawn at this n)
M0 = 64  # reference_batch (panel (b) is drawn at this m)
BREAKDOWN = ["phase4_attest_ms", "phase4_fresh_ms", "phase4_commit_ms", "phase4_committee_ms"]


def t_of(n):
    return (2 * n) // 3 + 1


def points(system, exp=RES):
    with open(exp / system / "experiment-reps/metrics.json") as f:
        for k, v in json.load(f)["points"].items():
            yield dict(x.split("=") for x in k.split("|")), v


def med(v, key):
    m = v.get(key)
    return m["median"] if isinstance(m, dict) and m.get("median") is not None else None


def primitives():
    """Exp. 0 medians (ms) by symbol, VeRedact-PQ."""
    return {p["symbol"]: v["median"] for p, v in points("veredact", ROOT / "exp00_primitives")}


def batches(system, rep=1):
    """One row per authorization batch (the per-request rows repeat the batch's Phase 4 columns)."""
    cols = ["committee_n", "batch_size", "sample", "phase3_ms", "phase4_batch_ms", *BREAKDOWN]
    d = pd.read_csv(RES / system / f"experiment-rep0{rep}/rows.csv", usecols=cols, low_memory=False)
    return d.drop_duplicates(["committee_n", "batch_size", "sample"])


def table_a_plotted_vs_complete():
    """A. Panel (a) at n=7: the plotted Phase-4 number vs the complete authorization cost per request."""
    plotted, complete = {}, {}
    for s in SYSTEMS:
        for p, v in points(s):
            if int(float(p["committee_n"])) != N0:
                continue
            m = int(float(p["batch_size"]))
            plotted.setdefault(m, {})[s] = med(v, "auth_per_request_ms")
            complete.setdefault(m, {})[s] = med(v, "auth_complete_per_request_ms")
    a = pd.DataFrame(plotted).T.sort_index()[SYSTEMS]
    c = pd.DataFrame(complete).T.sort_index()[SYSTEMS]
    out = pd.DataFrame(
        {
            "plotted_VR": a.veredact,
            "plotted_best_base": a[["S1", "S34", "S99"]].min(axis=1),
            "plotted_ratio": a.veredact / a[["S1", "S34", "S99"]].min(axis=1),
            "complete_VR": c.veredact,
            "complete_best_base": c[["S1", "S34", "S99"]].min(axis=1),
            "complete_ratio": c.veredact / c[["S1", "S34", "S99"]].min(axis=1),
        }
    )
    out.index.name = "m"
    return a.round(3), out.round(2)


def table_b_phase4_model(T):
    """B. Phase 4 per set at n=7 against m(T_V+2T_H) + m T_H + 2m T_H + t(T_S+T_V), and the remainder that the
    four timers do not cover (BatchAuth, Merkle proofs, the anchoring transaction's build + secp256k1 signing)."""
    b = batches("veredact")
    b = b[b.committee_n == N0].groupby("batch_size")[["phase4_batch_ms", *BREAKDOWN]].median()
    t = t_of(N0)
    model = pd.DataFrame(
        {
            "attest_model": b.index * (T["T_V"] + 2 * T["T_H"]),
            "fresh_model": b.index * T["T_H"],
            "commit_model": 2 * b.index * T["T_H"],
            "committee_model": t * (T["T_S"] + T["T_V"]),
        },
        index=b.index,
    )
    out = pd.DataFrame(
        {
            "attest": b.phase4_attest_ms,
            "attest_model": model.attest_model,
            "fresh": b.phase4_fresh_ms,
            "commit": b.phase4_commit_ms,
            "committee": b.phase4_committee_ms,
            "committee_model": model.committee_model,
            "phase4_total": b.phase4_batch_ms,
            "model_total": model.sum(axis=1),
            "untimed_remainder": b.phase4_batch_ms - b[BREAKDOWN].sum(axis=1),
        }
    )
    out["remainder_share"] = out.untimed_remainder / out.phase4_total
    out.index.name = "m"
    return out.round(3)


def table_c_fixed_vs_marginal():
    """C. Phase 4 = fixed + marginal.m, fitted per committee size (ms): what amortization can and cannot remove."""
    b = batches("veredact")
    rows = []
    for n, g in b.groupby("committee_n"):
        g = g.groupby("batch_size").phase4_batch_ms.median()
        slope, intercept = np.polyfit(g.index.to_numpy(float), g.to_numpy(float), 1)
        rows.append(
            {
                "n": n,
                "t": t_of(n),
                "fixed_ms": round(intercept, 3),
                "marginal_ms_per_request": round(slope, 4),
                "committee_ms": round(b[b.committee_n == n].phase4_committee_ms.median(), 3),
                "untimed_remainder_ms": round(
                    (b[b.committee_n == n].phase4_batch_ms - b[b.committee_n == n][BREAKDOWN].sum(axis=1)).median(), 3
                ),
            }
        )
    return pd.DataFrame(rows)


def table_d_per_set(T):
    """D. Panel (b) at m=64: one authorized set vs n, and Re-ZK against m t T_ZV."""
    out = {}
    for s in SYSTEMS:
        for p, v in points(s):
            if int(float(p["batch_size"])) == M0:
                out.setdefault(int(float(p["committee_n"])), {})[s] = med(v, "batch_total_ms")
    d = pd.DataFrame(out).T.sort_index()[SYSTEMS]
    d["rezk_model"] = [M0 * t_of(n) * T["T_ZV"] for n in d.index]
    d["rezk_measured_minus_VR"] = d["veredact-re-zk"] - d.veredact
    d["S1_model_t_x_2_ECDSA"] = [M0 * t_of(n) * 2 * 0.0266 for n in d.index]  # S1's T_V^c (Exp. 0)
    d.index.name = "n"
    return d.round(2)


def table_e_operating_point():
    """E. The round sizes CORA actually produces (Exp. 1, run 1): which part of the m axis is ever used."""
    cols = ["sweep", "rate_rps", "batch_id", "batch_size"]
    d = pd.read_csv(ROOT / "exp01_redaction_throughput/veredact/experiment-rep01/rows.csv", usecols=cols)
    d = d[d.sweep == "rate"].dropna(subset=["batch_id"])
    r = d.groupby(["rate_rps", "batch_id"]).first()
    return r.groupby("rate_rps").batch_size.agg(rounds="size", m_mean="mean", m_median="median", m_max="max").round(1)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    T = primitives()
    print("Primitives (Exp. 0, ms):", {k: round(T[k], 4) for k in ("T_S", "T_V", "T_ZV", "T_H")}, "\n")
    plotted, both = table_a_plotted_vs_complete()
    print(f"A1. Plotted Fig. 4(a) auth_per_request_ms at n={N0}\n", plotted.to_string(), "\n")
    print("A2. Plotted (Phase 4 / m) vs complete (Phase 3 + Phase 4 / m)\n", both.to_string(), "\n")
    print(f"B. Phase 4 per set at n={N0} vs the Exp. 0 cost model\n", table_b_phase4_model(T).to_string(), "\n")
    print("C. Phase 4 fitted as fixed + marginal x m\n", table_c_fixed_vs_marginal().to_string(index=False), "\n")
    print(f"D. One set of m={M0} vs n (Fig. 4(b))\n", table_d_per_set(T).to_string(), "\n")
    print("E. Round sizes CORA produced in Exp. 1 (run 1)\n", table_e_operating_point().to_string())
