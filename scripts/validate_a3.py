"""Audit A3 validation (small configuration): VeRedact-PQ Exp. 1 points on the pilot ledger with Besu, with the
requester/system core split, reporting decided %, throughput, executor round cost and revalidations.
Usage (server, Besu up): VRPQ_SIG_BACKEND=oqs VRPQ_BESU_KEY=... .venv/bin/python scripts/validate_a3.py"""

# ruff: noqa: E501  (diagnostic report lines)
import argparse
import statistics as st

from veredact_bench.evaluation.experiments.exp01_redaction_throughput import run_point
from veredact_bench.utils import cpus
from veredact_bench.utils.config import load
from veredact_bench.utils.log import get_logger


class Collect:
    def __init__(self, log):
        self.log, self.rows = log, []

    def dataset(self, *_):
        pass

    def row(self, **r):
        self.rows.append(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pilot")
    ap.add_argument("--rates", type=int, nargs="+", default=[100, 250])
    ap.add_argument("--skews", type=float, nargs="+", default=[0.8])
    a = ap.parse_args()
    cfg = load(a.tier, "exp01_redaction_throughput")
    x = cfg["experiment"]
    w0, w1 = x["warmup_s"], x["warmup_s"] + x["duration_s"]
    _, sys_cpus = cpus.split(x["requester_cores"])
    if sys_cpus and cfg["ledger"]["backend"] == "besu":
        cpus.pin_besu(sys_cpus)
    for rate in a.rates:
        for s in a.skews:
            c = Collect(get_logger())
            run_point(cfg, "veredact", rate, s, c, "validate")
            win = [r for r in c.rows if r["in_window"] == 1 and not r["fault"]]
            done = [
                r
                for r in c.rows
                if r["status"] == "finalized"
                and not r["fault"]
                and r["latency_ms"] != ""
                and w0 <= r["submit_s"] + r["latency_ms"] / 1000 < w1
            ]
            batches = {r["batch_id"]: (r["redact_crypto_ms"], r["batch_size"]) for r in c.rows if r["batch_id"] != ""}
            print(
                f"A3 rate={rate} s={s}: decided {sum(r['status'] in ('finalized', 'rejected', 'failed') for r in win) / len(win):.0%}"
                f" | throughput {len(done) / x['duration_s']:.1f}/s | round p50 {st.median(v[0] for v in batches.values()):.0f} ms"
                f" x batch p50 {st.median(v[1] for v in batches.values()):.0f} | revalidations/request "
                f"{sum(int(r['revalidations']) for r in win) / len(win):.2f} | on time "
                f"{sum(r['submit_s'] != '' and r['submit_s'] < w1 for r in win) / len(win):.0%}",
                flush=True,
            )
    if sys_cpus and cfg["ledger"]["backend"] == "besu":
        cpus.pin_besu(None)


if __name__ == "__main__":
    main()
