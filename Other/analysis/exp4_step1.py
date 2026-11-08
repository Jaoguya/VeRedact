"""Issue #8 step 1: why VeRedact-PQ loses in Exp. 4. Diagnostic only, never a paper number.

Reads release run-2026-11-03 unpacked into Benchmark/results/ and prints the tables the verdict cites:
  python Other/analysis/exp4_step1.py
"""

import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Benchmark/results"
RES = ROOT / "exp04_verification_time"
SYSTEMS = ["veredact", "S1", "S13"]
PARTS = ["response", "rai_mp", "attest", "committee", "state", "cp", "zk"]


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


def nodes():
    """Verified evidence nodes per n_Q (rows.csv, run 1, routine, no fault): q, a_Q, z_Q, c_Q."""
    d = pd.read_csv(RES / "veredact/experiment-rep01/rows.csv", low_memory=False)
    d = d[(d.fault_kind == "none") & (d.deep_fraction == 0)]
    cols = ["nodes_req", "nodes_auth", "nodes_trans", "nodes_cp", "records_per_batch"]
    return d.groupby("n_Q")[cols].median()


def table_a_routine():
    """A. Fig. (a) at d_Q = 0: verification (ms) per n_Q and system, and VeRedact-PQ's ratio to each."""
    t = {}
    for s in SYSTEMS:
        for p, v in points(s):
            if p["fault_kind"] == "none" and float(p["deep_fraction"]) == 0:
                t.setdefault(int(p["n_Q"]), {})[s] = med(v, "verify_ms")
    a = pd.DataFrame(t).T.sort_index()
    a["VeRedact/S13"] = a.veredact / a.S13
    a["S1/VeRedact"] = a.S1 / a.veredact
    return a.round(1)


def table_b_breakdown(T):
    """B. Fig. (b) at n_Q = 10^4, d_Q = 0: each bar vs its cost model from the measured primitives."""
    n = nodes().loc[10000]
    v = next(
        v
        for p, v in points("veredact")
        if p["n_Q"] == "10000" and p["fault_kind"] == "none" and float(p["deep_fraction"]) == 0
    )
    q, a, z, c = n.nodes_req, n.nodes_auth, n.nodes_trans, n.nodes_cp
    model = {
        "attest": (q * T["T_V"], f"q*T_V = {q:.0f}*{T['T_V']:.3f}"),
        "committee": (a * 5 * T["T_V"], f"a_Q*t*T_V = {a:.0f}*5*{T['T_V']:.3f}"),
        "state": (z * T["T_CH"], f"z_Q*T_CH = {z:.0f}*{T['T_CH']:.3f}"),
        "cp": (c * T["T_V"], f"c_Q*T_V = {c:.0f}*{T['T_V']:.3f}"),
    }
    rows = []
    for k in PARTS:
        ms = med(v, f"verify_{k}_ms")
        m, how = model.get(k, (None, ""))
        rows.append(
            {
                "part": k,
                "measured_ms": round(ms, 1),
                "model_ms": m and round(m, 1),
                "model": how,
                "unexplained_ms": m and round(ms - m, 1),
            }
        )
    rows.append({"part": "total", "measured_ms": round(med(v, "verify_ms"), 1)})
    return pd.DataFrame(rows), {
        "q": q,
        "a_Q": a,
        "z_Q": z,
        "c_Q": c,
        "z_Q/q": round(z / q, 3),
        "2*T_CH implies z_Q": round(med(v, "verify_state_ms") / (2 * T["T_CH"])),
    }


def table_c_escalation(T):
    """C. Fig. (a) slope at n_Q = 10^4: extra time per escalated request vs T_ZV."""
    rows = []
    base = None
    for p, v in sorted(points("veredact"), key=lambda pv: float(pv[0]["deep_fraction"])):
        if p["n_Q"] != "10000" or p["fault_kind"] != "none":
            continue
        d = float(p["deep_fraction"])
        tot, zk = med(v, "verify_ms"), med(v, "verify_zk_ms")
        base = base or (tot, zk)
        k = d * 10000
        rows.append(
            {
                "d_Q/n_Q": d,
                "verify_ms": round(tot),
                "zk_ms": round(zk),
                "zk_ms per deep": k and round((zk - base[1]) / k, 3),
                "total delta per deep": k and round((tot - base[0]) / k, 3),
                "model d_Q*T_ZV": round(k * T["T_ZV"]),
            }
        )
    return pd.DataFrame(rows)


def table_d_faults():
    """D. Fig. (c): per fault class and fraction, invalid rejected (detection) and valid accepted."""
    rows = []
    for s in SYSTEMS:
        for p, v in points(s):
            if p["fault_kind"] != "none":
                rows.append(
                    {
                        "system": s,
                        "n_Q": int(p["n_Q"]),
                        "kind": p["fault_kind"],
                        "f": float(p["inject_fraction"]),
                        "injected": v["injected"],
                        "invalid_rejected": v["detection_rate"],
                        "valid_accepted": v["valid_acceptance_rate"],
                    }
                )
    d = pd.DataFrame(rows)
    return d.pivot_table(
        index=["n_Q", "kind", "f"], columns="system", values=["invalid_rejected", "valid_accepted"]
    ).round(2)


def table_e_generation():
    """E. Counter-view: response generation (retrieval_ms, untimed in Fig. 6) per n_Q, run 1 medians."""
    out = {}
    for s in SYSTEMS:
        d = pd.read_csv(
            RES / s / "experiment-rep01/rows.csv",
            low_memory=False,
            usecols=["n_Q", "fault_kind", "deep_fraction", "retrieval_ms"],
        )
        d = d[(d.fault_kind == "none") & (d.deep_fraction == 0)]
        out[s] = d.groupby("n_Q").retrieval_ms.median()
    return pd.DataFrame(out).round(1)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    T = primitives()
    print("Primitives (Exp. 0, ms):", {k: round(T[k], 4) for k in ("T_V", "T_ZV", "T_CH", "T_H")}, "\n")
    print("Nodes per query (rows.csv run 1)\n", nodes().to_string(), "\n")
    print("A. Routine verification (ms), Fig. (a) at d_Q = 0\n", table_a_routine().to_string(), "\n")
    b, z = table_b_breakdown(T)
    print("B. Breakdown at n_Q = 10^4, d_Q = 0 vs cost model\n", b.to_string(index=False), "\n", z, "\n")
    print("C. Escalation at n_Q = 10^4\n", table_c_escalation(T).to_string(index=False), "\n")
    print("D. Fault classes\n", table_d_faults().to_string(), "\n")
    print("E. Response generation (ms), not in Fig. 6\n", table_e_generation().to_string())
