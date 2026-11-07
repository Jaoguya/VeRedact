"""Issue #5 step 1: why VeRedact-PQ loses in Exp. 1. Diagnostic only, never a paper number.

Reads release run-2026-11-03 unpacked into Benchmark/results/ and prints the four tables the verdict cites:
  python Other/analysis/exp1_step1.py
"""

import json
import pathlib

import numpy as np
import pandas as pd

RES = pathlib.Path(__file__).resolve().parents[2] / "Benchmark/results/exp01_redaction_throughput"
SYSTEMS = ["veredact", "veredact-fixed-batch", "veredact-cora-no-sfmr", "veredact-per-request", "S1", "S13", "S27", "S34"]


def rows(system, cols):
    d = pd.read_csv(RES / system / "experiment-rep01/rows.csv", usecols=cols, low_memory=False)
    return d[d.sweep == "rate"]


def table_a_summary():
    """A. Per rate, every system (metrics.json): throughput, re-proofs per decided request, p95, censored."""
    out = []
    for s in SYSTEMS:
        for k, v in json.load(open(RES / s / "experiment-reps/metrics.json"))["points"].items():
            p = dict(x.split("=") for x in k.split("|"))
            d = v.get("decided") or 0
            out.append(
                dict(
                    system=s,
                    sweep=p["sweep"],
                    rate=int(p["rate_rps"]),
                    s=float(p["zipf_s"]),
                    throughput=round(v.get("throughput_per_s", 0), 1),
                    reproofs_per_decided=round(v["revalidations"] / d, 2) if d else None,
                    on_time=round(v.get("submitted_on_time", np.nan), 2),
                    p95_s=round(v.get("latency_ms", {}).get("p95", np.nan) / 1000, 1),
                    p95_lower_bound=v.get("latency_p95_lower_bound"),
                    censored=round(v.get("latency_censored_fraction", np.nan), 2),
                    adapt_per_1000=round(v.get("pqch_adaptations_per_1000", np.nan)),
                )
            )
    return pd.DataFrame(out)


def table_b_rounds(system):
    """B. Per rate: requests per round m, batches |Omega|, time split of a round (rows.csv)."""
    cols = ["sweep", "rate_rps", "batch_id", "batch_size", "batch_batches", "redact_crypto_ms", "finality_ledger_ms"]
    r = rows(system, cols).dropna(subset=["batch_id"]).groupby(["rate_rps", "batch_id"]).first()
    return r.groupby("rate_rps").agg(
        rounds=("batch_size", "size"),
        m_mean=("batch_size", "mean"),
        m_max=("batch_size", "max"),
        omega_mean=("batch_batches", "mean"),
        crypto_ms=("redact_crypto_ms", "mean"),
        finality_ms=("finality_ledger_ms", "mean"),
    ).round(1)


def table_c_churn():
    """C. VeRedact-PQ: validations done by the VPS vs redactions finished; proof age at validation."""
    cols = ["sweep", "rate_rps", "status", "revalidations", "submit_s", "proof_age_ms", "client_lag_ms"]
    d = rows("veredact", cols)
    out = []
    for rate, g in d.groupby("rate_rps"):
        sub = g[g.status != "not_submitted"]
        validations = len(sub) + sub.revalidations.sum()
        span = sub.submit_s.max() - sub.submit_s.min()
        fin = (g.status == "finalized").sum()
        out.append(
            dict(
                rate=rate,
                validations_per_s=round(validations / span),
                finalized_per_s=round(fin / span),
                wasted_validations=f"{1 - fin / validations:.0%}",
                proof_age_median_ms=round(g.proof_age_ms.median()),
                client_lag_median_ms=round(g.client_lag_ms.median()),
                not_submitted=int((g.status == "not_submitted").sum()),
            )
        )
    return pd.DataFrame(out)


def table_d_sharing(batches=int(np.ceil(1e5 / 256))):
    """D. Expected PQCH adaptations per 1,000 redactions if a round of m requests draws batches ~ Zipf(s)."""
    def expected(m, s):
        w = 1 / np.arange(1, batches + 1) ** s
        p = w / w.sum()
        return round(1000 * (1 - (1 - p) ** m).sum() / m)

    return pd.DataFrame({f"m={m}": {s: expected(m, s) for s in (0, 0.4, 0.8, 1.2)} for m in (8, 50, 140, 256)})


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    a = table_a_summary()
    print("A. Summary per point (metrics.json)\n", a.to_string(index=False), "\n")
    for s in ("veredact", "S27"):
        print(f"B. Rounds, {s} (rows.csv)\n", table_b_rounds(s).to_string(), "\n")
    print("C. VeRedact-PQ validation churn (rows.csv)\n", table_c_churn().to_string(index=False), "\n")
    print("D. Expected adaptations / 1,000 under Zipf over 391 batches (index = s)\n", table_d_sharing().to_string())
