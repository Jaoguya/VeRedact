"""Issue #9 step 1: what Exp. 5 actually measures, and where VeRedact-PQ loses. Diagnostic only.

Reads release run-2026-11-03 unpacked into Benchmark/results/ and prints the tables the verdict cites:
  python Other/analysis/exp5_step1.py
"""

import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Benchmark/results"
RES = ROOT / "exp05_blockchain_overhead"
BLOCK_MS = 2000  # configs: ledger.block_period_s = 2
SIG = 3309  # ML-DSA-65 signature; abi-padded to 3328
WORD = 32
CP_WORDS = 9  # VeRedactRegistry.Checkpoint: chDigest, mr, rDigest, rRli, vRli, epoch, vb, ts, sigDigest
RLP = 106  # measured envelope: 4046 - calldata(|Omega|=1); nonce, gasPrice, gas, to, value, v, r, s


def rows():
    out = []
    for rep in (1, 2, 3):
        d = pd.read_csv(RES / f"veredact/experiment-rep0{rep}/rows.csv", low_memory=False)
        d["rep"] = rep
        out.append(d)
    return pd.concat(out)


def points():
    with open(RES / "veredact/experiment-reps/metrics.json") as f:
        for k, v in json.load(f)["points"].items():
            yield dict(x.split("=") for x in k.split("|")), v


def pad(n):
    return -(-n // WORD) * WORD


def calldata_finalize(omega):
    """finalizeRedaction(bytes32 bid, uint256[] bs, Checkpoint[] cps, bytes[] sigs) — exact ABI encoding."""
    head = 4 + WORD + 3 * WORD  # selector, bid, three array offsets
    bs = WORD + omega * WORD
    cps = WORD + omega * CP_WORDS * WORD
    sigs = WORD + omega * WORD + omega * (WORD + pad(SIG))  # length, per-element offsets, (length, padded bytes)
    return head + bs + cps + sigs


def table_a_tx_size():
    """A. Transaction size: measured vs the exact ABI model, and the ML-DSA share."""
    m = {}
    for p, v in points():
        m.setdefault(int(float(p["affected_batches"])), {})[int(float(p["validators"]))] = v["finalize_tx_bytes"][
            "median"
        ]
    t = pd.DataFrame(m).T.sort_index()
    t.columns = [f"measured n={c}" for c in t.columns]
    t["model (ABI + RLP)"] = [calldata_finalize(o) + RLP for o in t.index]
    t["per affected batch"] = t["measured n=7"] / t.index
    t["of which sigma_b' (3328 B)"] = (pad(SIG) * t.index) / t["measured n=7"]
    t.index.name = "|Omega_e|"
    return t.round(3)


def table_b_latency():
    """B. Finalization latency against the QBFT block period: this is phase, not consensus cost.

    Hypothesis: a round submits its finalization after its own execution work W, so the wait for the next
    block is BLOCK_MS - (W mod BLOCK_MS). The last column is that implied W; it should grow linearly with
    |Omega_e| (one SFMR update + one PQCH adaptation per affected batch)."""
    d = rows()
    by = d.groupby(["validators", "affected_batches"]).finalize_ms
    g = by.agg(["min", "median", "max", "std", "count"])
    g["< block period"] = by.apply(lambda s: (s < BLOCK_MS).mean())
    g["implied W (ms)"] = BLOCK_MS - g["median"]
    w = g["implied W (ms)"].groupby("affected_batches").mean()
    fit = (w.loc[32] - w.loc[4]) / (32 - 4)
    return g.round(1), round(fit, 1), round(w.loc[4] - 4 * fit, 1)


def table_c_validators():
    """C. What the validator sweep resolves: the spread between 4, 7 and 10 against the within-point spread."""
    d = rows()
    med = d.groupby(["affected_batches", "validators"]).finalize_ms.median().unstack()
    out = pd.DataFrame(
        {
            "min over n": med.min(axis=1),
            "max over n": med.max(axis=1),
            "spread over n (ms)": med.max(axis=1) - med.min(axis=1),
            "within-point std (ms)": d.groupby("affected_batches").finalize_ms.std(),
        }
    )
    out["spread / std"] = out["spread over n (ms)"] / out["within-point std (ms)"]
    out["tx bytes identical over n"] = (
        d.groupby(["affected_batches", "validators"]).finalize_tx_bytes.median().unstack().nunique(axis=1) == 1
    )
    return out.round(2)


def table_d_per_redaction():
    """D. On-chain cost per finalized redaction. VeRedact-PQ measured; baselines modelled from the contract ABI
    (BaselineRedactionLog.recordRedaction / recordRedactionWithAcc) — a prediction until Exp. 5 measures them."""

    def baseline(evidence, acc=0):
        head = 4 + 3 * WORD + WORD + (2 * WORD if acc else 0)  # selector, tid, commit, version, offsets
        return head + WORD + pad(evidence) + (WORD + pad(acc) if acc else 0) + RLP

    model = {
        "S1 [1] recordRedactionWithAcc (BLS 48 B + RSA-3072 acc)": baseline(48, 384),
        "S13 [13] recordRedaction (RSA-3072 tag 385 B)": baseline(385),
        "S27 [27] recordRedaction (32 B)": baseline(32),
        "S34 [34] recordRedaction (RSA-3072 r 384 B)": baseline(384),
    }
    # VeRedact-PQ at the round composition Exp. 1 measured (run 1, rate sweep)
    cols = ["sweep", "rate_rps", "batch_id", "batch_size", "batch_batches"]
    e1 = pd.read_csv(ROOT / "exp01_redaction_throughput/veredact/experiment-rep01/rows.csv", usecols=cols)
    e1 = e1[e1.sweep == "rate"].dropna(subset=["batch_id"]).groupby(["rate_rps", "batch_id"]).first()
    g = e1.groupby("rate_rps")[["batch_size", "batch_batches"]].mean()
    vr = pd.DataFrame(
        {
            "m (redactions per round)": g.batch_size.round(1),
            "|Omega_e| per round": g.batch_batches.round(1),
            "tx bytes (model)": [calldata_finalize(round(o)) + RLP for o in g.batch_batches],
            "transactions per redaction": (1 / g.batch_size).round(4),
        }
    )
    vr["bytes per redaction"] = (vr["tx bytes (model)"] / g.batch_size).round(0)
    return pd.Series(model), vr


def table_e_axis():
    """E. The |Omega_e| the experiment sweeps vs the |Omega_e| the system produces (Exp. 1, run 1)."""
    cols = ["sweep", "rate_rps", "batch_id", "batch_batches"]
    e1 = pd.read_csv(ROOT / "exp01_redaction_throughput/veredact/experiment-rep01/rows.csv", usecols=cols)
    e1 = e1[e1.sweep == "rate"].dropna(subset=["batch_id"]).groupby(["rate_rps", "batch_id"]).first()
    swept = sorted({int(float(p["affected_batches"])) for p, _ in points()})
    return swept, e1.groupby("rate_rps").batch_batches.agg(["min", "mean", "median", "max"]).round(1)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    print("A. Redaction-finalization transaction size\n", table_a_tx_size().to_string(), "\n")
    b, per_batch, fixed = table_b_latency()
    print(f"B. Finalization latency vs the {BLOCK_MS} ms block period\n", b.to_string())
    print(f"   implied pre-submission work W = {fixed} ms + {per_batch} ms per affected batch\n")
    print("C. What the validator sweep resolves\n", table_c_validators().to_string(), "\n")
    base, vr = table_d_per_redaction()
    print("D1. Baseline signed transaction per redaction (ABI model, prediction)\n", base.to_string(), "\n")
    print("D2. VeRedact-PQ per redaction at Exp. 1's measured round composition\n", vr.to_string(), "\n")
    swept, produced = table_e_axis()
    print("E. Axis swept by Exp. 5:", swept)
    print("   |Omega_e| produced in Exp. 1\n", produced.to_string())
