"""Issue #7 step 1: why VeRedact-PQ loses in Exp. 3. Diagnostic only, never a paper number.

Reads release run-2026-11-03 unpacked into Benchmark/results/ and prints the tables the verdict cites:
  python Other/analysis/exp3_step1.py
"""

import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Benchmark/results"
RES = ROOT / "exp03_audit_efficiency"
VR = ["veredact", "veredact-shared-evidence", "veredact-per-record"]
SYSTEMS = [*VR, "S1", "S13"]
RPB = "64"  # veredact.reference_batch: the records_per_batch the figure draws
SIG = 3309  # ML-DSA-65 signature (pqsig.py sig_size); the one constant the byte model needs
N_MAX = 10000


def points(system, exp=RES):
    with open(exp / system / "experiment-reps/metrics.json") as f:
        for k, v in json.load(f)["points"].items():
            yield dict(x.split("=") for x in k.split("|")), v


def med(v, key):
    m = v.get(key)
    return m["median"] if isinstance(m, dict) and m.get("median") is not None else m


def at(system, field, rpb=RPB):
    """field per n_Q at the drawn records_per_batch (baselines have no batches: every point counts)."""
    out = {}
    for p, v in points(system):
        if p["records_per_batch"] in (rpb, "n/a (no batches)"):
            out[int(float(p["n_Q"]))] = med(v, field)
    return out


def nodes(system="veredact", rpb=64):
    """Verified evidence nodes per n_Q (rows.csv, run 1): q, a_Q, z_Q, c_Q."""
    cols = ["records_per_batch", "n_Q", "nodes_req", "nodes_auth", "nodes_trans", "nodes_cp", "evidence_bytes"]
    d = pd.read_csv(RES / system / "experiment-rep01/rows.csv", usecols=cols, low_memory=False)
    return d[d.records_per_batch == rpb].groupby("n_Q")[cols[2:]].median()


def table_a_three_views():
    """A. The three panels at the drawn records_per_batch: generation, size, verification; our ratio to each."""
    out = {}
    for f in ("retrieval_ms", "evidence_bytes", "verify_ms"):
        t = pd.DataFrame({s: at(s, f) for s in SYSTEMS}).sort_index()
        t["VR/S1"] = t.veredact / t.S1
        t["VR/S13"] = t.veredact / t.S13
        out[f] = t
    return out


def table_b_bytes_model():
    """B. Where the response bytes are, from veredact.py:487-513 with the measured node counts (n_Q = 10^4)."""
    n = nodes().loc[N_MAX]
    q, a, z = int(n.nodes_req), int(n.nodes_auth), int(n.nodes_trans)
    auth_one = 16 + 32 + 32 + 8 + 8 + 5 * (8 + SIG)  # _auth_bytes(), t = 5
    trans_cp = (32 * 2 + 32 * 4) + (8 * 4 + 32 * 3 + SIG)  # trans_bytes + cp_bytes, per (b, v_b) transition
    parts = {
        "per-record alpha_i (ML-DSA)": q * SIG,
        "per-record digests (eta, MP_B, C_VR, ...)": q * 32 * 8,
        "per-transition checkpoint sigma_b' (ML-DSA)": z * SIG,
        "per-transition fields (Theta_b, Xi_b, A_b')": z * (trans_cp - SIG),
        "per-authorization (t=5 committee ML-DSA + fields)": a * auth_one,
        "RAI index entries (128 B each)": 128 * q,
        "audit-service signature": SIG,
    }
    total = int(n.evidence_bytes)
    t = pd.DataFrame({"bytes": parts})
    t["share"] = t.bytes / total
    t.loc["RAI multiproof (residual)"] = [total - t.bytes.sum(), (total - t.bytes.sum()) / total]
    t.loc["TOTAL (measured)"] = [total, 1.0]
    sigs = q * SIG + z * SIG + a * 5 * SIG + SIG
    return t.round(4), {"q": q, "a_Q": a, "z_Q": z, "signature bytes": sigs, "signature share": round(sigs / total, 3)}


def table_c_sharing():
    """C. Why SAVER is only ~1.4x Shared-Evidence: which node types share, at the drawn records_per_batch."""
    s, sh = nodes("veredact"), nodes("veredact-shared-evidence")
    t = pd.DataFrame(
        {
            "q (request)": s.nodes_req,
            "a_Q (authorization)": s.nodes_auth,
            "z_Q (transition)": s.nodes_trans,
            "c_Q (checkpoint)": s.nodes_cp,
            "SAVER nodes": s[["nodes_req", "nodes_auth", "nodes_trans", "nodes_cp"]].sum(axis=1),
            "Shared-Evidence nodes": sh[["nodes_req", "nodes_auth", "nodes_trans", "nodes_cp"]].sum(axis=1),
        }
    )
    t["node ratio"] = t["Shared-Evidence nodes"] / t["SAVER nodes"]
    v, vsh = at("veredact", "verify_ms"), at("veredact-shared-evidence", "verify_ms")
    t["verify ratio"] = [vsh[n] / v[n] for n in t.index]
    t["records per transition"] = t["q (request)"] / t["z_Q (transition)"]
    return t.round(2)


def table_d_verify_breakdown():
    """D. Where the verification time goes. Exp. 4 run 1 at d_Q = 0 is the same routine path as Exp. 3."""
    cols = [
        "n_Q",
        "deep_fraction",
        "fault_kind",
        "verify_ms",
        "verify_response_ms",
        "verify_rai_mp_ms",
        "verify_attest_ms",
        "verify_committee_ms",
        "verify_state_ms",
        "verify_cp_ms",
    ]
    d = pd.read_csv(ROOT / "exp04_verification_time/veredact/experiment-rep01/rows.csv", usecols=cols)
    d = d[(d.fault_kind == "none") & (d.deep_fraction == 0)]
    g = d.groupby("n_Q")[cols[3:]].median()
    share = (g.loc[N_MAX] / g.loc[N_MAX, "verify_ms"]).round(3)
    T = {p["symbol"]: v["median"] for p, v in points("veredact", ROOT / "exp00_primitives")}
    n = nodes().loc[N_MAX]
    model = {
        "verify_attest_ms": n.nodes_req * T["T_V"],
        "verify_committee_ms": n.nodes_auth * 5 * T["T_V"],
        "verify_state_ms": n.nodes_trans * T["T_CH"],
        "verify_cp_ms": n.nodes_cp * T["T_V"],
    }
    cmp_ = pd.DataFrame({"measured_ms": g.loc[N_MAX], "share": share, "model_ms": pd.Series(model)}).dropna()
    cmp_["measured/model"] = cmp_.measured_ms / cmp_.model_ms
    cmp_["excess_ms_per_record"] = (cmp_.measured_ms - cmp_.model_ms) / N_MAX
    return g.round(1), cmp_.round(3)


def table_e_s13():
    """E. Scheme [13]: one aggregate decision; generation is one RSA non-membership witness per queried block."""
    gen, size, ver = at("S13", "retrieval_ms"), at("S13", "evidence_bytes"), at("S13", "verify_ms")
    witness_ms = gen[10] / 10  # n_Q = 10 touches 10 distinct blocks: one witness each
    return pd.DataFrame(
        {
            "generation_ms": gen,
            "verify_ms": ver,
            "response_bytes": size,
            "implied blocks (gen / one witness)": {n: gen[n] / witness_ms for n in gen},  # saturates at 391
            "decisions returned": dict.fromkeys(gen, 1),
        }
    ).round(1)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    print("Nodes per query (rows.csv run 1, records_per_batch = 64)\n", nodes().to_string(), "\n")
    for f, t in table_a_three_views().items():
        print(f"A. {f} per n_Q (records_per_batch = {RPB})\n", t.to_string(), "\n")
    b, z = table_b_bytes_model()
    print(f"B. Response bytes at n_Q = {N_MAX}\n", b.to_string(), "\n", z, "\n")
    print("C. Evidence sharing: SAVER vs Shared-Evidence\n", table_c_sharing().to_string(), "\n")
    g, cmp_ = table_d_verify_breakdown()
    print("D1. Verification breakdown (ms, Exp. 4 run 1, d_Q = 0)\n", g.to_string(), "\n")
    print(f"D2. At n_Q = {N_MAX} vs the Exp. 0 cost model\n", cmp_.to_string(), "\n")
    print("E. Scheme [13]\n", table_e_s13().to_string())
