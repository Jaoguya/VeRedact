"""Diagnostic (not a paper experiment): is VeRedact-PQ's Exp. 1 revalidation storm a protocol property or an
artefact of requesters sharing the system's CPUs on one host?

Runs the same Exp. 1 points twice on the server (Besu up, liboqs):
  shared    every thread on every CPU (as in the experiment tier)
  isolated  requester + re-prover threads on half of the physical cores; VPS workers, executor and the Besu
            containers on the other half — emulates requesters proving on their own machines
and reports, per point: decided / offered, submitted on time, revalidations per request, and the proof's age
when the VPS validates it (proved -> validated). Writes results/diagnostics/core_isolation.json.

Usage (server): VRPQ_SIG_BACKEND=oqs VRPQ_BESU_KEY=... .venv/bin/python scripts/diag_core_isolation.py
"""

import argparse
import copy
import glob
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from veredact_bench.evaluation.experiments.exp01_redaction_throughput import run_point
from veredact_bench.utils.config import REPO_ROOT, load
from veredact_bench.utils.log import get_logger


def partition():
    """Physical cores split in two; each half keeps both hyperthreads of its cores."""
    cores = defaultdict(list)
    for d in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology"):
        cpu = int(d.split("/cpu")[-1].split("/")[0])
        key = (Path(d, "physical_package_id").read_text().strip(), Path(d, "core_id").read_text().strip())
        cores[key].append(cpu)
    groups = [sorted(v) for _, v in sorted(cores.items())]
    half = len(groups) // 2
    return {"requesters": sum(groups[:half], []), "system": sum(groups[half:], [])}


def pin_besu(cpus):
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    for n in (n for n in names if n.startswith("besu-validator")):
        subprocess.run(
            ["docker", "update", "--cpuset-cpus", ",".join(map(str, cpus)), n], check=True, capture_output=True
        )


class Collect:
    def __init__(self, log):
        self.log, self.rows = log, []

    def dataset(self, *_):
        pass

    def row(self, **r):
        self.rows.append(r)


def summary(rows, end):
    win = [r for r in rows if r["in_window"] == 1 and not r["fault"]]
    num = lambda k: [float(r[k]) for r in win if r[k] not in ("", None)]
    age, lag = sorted(num("proof_age_ms")), sorted(num("client_lag_ms"))
    q = lambda xs, p: round(xs[min(len(xs) - 1, int(p * len(xs)))], 1) if xs else None
    return {
        "offered": len(win),
        "decided": round(sum(r["status"] in ("finalized", "rejected", "failed") for r in win) / len(win), 3),
        "submitted_on_time": round(sum(r["submit_s"] != "" and r["submit_s"] < end for r in win) / len(win), 3),
        "revalidations_per_request": round(sum(int(r["revalidations"]) for r in win) / len(win), 2),
        "proof_age_ms_p50": q(age, 0.5),
        "proof_age_ms_p95": q(age, 0.95),
        "client_lag_ms_p50": q(lag, 0.5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rates", type=int, nargs="+", default=[100, 250])
    ap.add_argument("--skews", type=float, nargs="+", default=[0.0, 0.8])
    a = ap.parse_args()
    log = get_logger()
    base = load("experiment", "exp01_redaction_throughput")
    end = base["experiment"]["warmup_s"] + base["experiment"]["duration_s"]
    part, allcpus = partition(), sorted(sum(partition().values(), []))
    log.info(f"partition: {part}")
    out = {"partition": part, "points": []}
    for mode in ("shared", "isolated"):
        cfg = copy.deepcopy(base)
        cfg["experiment"]["cpu_pin"] = part if mode == "isolated" else None
        pin_besu(part["system"] if mode == "isolated" else allcpus)
        for rate in a.rates:
            for s in a.skews:
                c = Collect(log)
                run_point(cfg, "veredact", rate, s, c, "diag")
                r = {"mode": mode, "rate": rate, "zipf_s": s, **summary(c.rows, end)}
                out["points"].append(r)
                log.info(f"DIAG {r}")
    pin_besu(allcpus)
    dest = REPO_ROOT / "results" / "diagnostics" / "core_isolation.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    log.info(f"-> {dest}")


if __name__ == "__main__":
    main()
