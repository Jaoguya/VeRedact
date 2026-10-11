"""Result writer: results/<experiment>/<method>/<tier>/ per (experiment, method, tier).

    rows.csv              raw per-request / per-sample measurements (never pre-aggregated)
    metrics.json          summary computed from rows.csv with veredact_bench.metrics (see summaries.py)
    config_resolved.yaml  the fully composed config the run used
    run_info.json         git commit + dirty flag, timestamps, runtime, hardware, library versions,
                          signature backend, seed, dataset ids, notes
    run.log               the run's log

Idempotent: a method whose metrics.json exists is skipped unless force=True; a forced re-run replaces the
whole folder (never a silent partial overwrite).
"""

import csv
import json
import os
import platform
import shutil
import subprocess
import time
from importlib import metadata

from veredact_bench.evaluation.summaries import summarize
from veredact_bench.utils.config import REPO_ROOT, dump
from veredact_bench.utils.log import add_file, get_logger, remove

LIBS = (
    "numpy",
    "omegaconf",
    "pqcrypto",
    "cryptography",
    "gmpy2",
    "coincurve",
    "py_arkworks_bls12381",
    "matplotlib",
    "vrpq_stark",
    "liboqs-python",
    "web3",
)


def _git(*args):
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return "unavailable"


def environment() -> dict:
    fp = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                fp["cpu"] = line.split(":", 1)[1].strip()
                break
        fp["mem_gb"] = round(int(open("/proc/meminfo").readline().split()[1]) / 1048576, 1)
    except OSError:
        fp["cpu"] = (
            subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
            or platform.processor()
        )
    versions = {}
    for lib in LIBS:
        try:
            versions[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            versions[lib] = "not installed"
    fp["libraries"] = versions
    try:
        from veredact_bench.methods.veredact.crypto.pqsig import load_pqsig

        fp["signature_backend"] = load_pqsig().name
    except Exception as e:  # recorded, not hidden
        fp["signature_backend"] = f"unavailable: {e}"
    return fp


def show(path) -> str:
    """Path for log lines: relative to the repo when inside it."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def method_dir(method: str) -> str:
    return method.replace(":", "-")  # folder-safe method name


class RunWriter:
    def __init__(self, cfg: dict, force: bool = False):
        self.cfg, self.force = cfg, force
        self.exp, self.tier = cfg["experiment"]["id"], cfg["meta"]["tier"]
        self.log = get_logger()
        self._env = environment()
        self._git = {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}
        self.method = None

    def path(self, method: str):
        return REPO_ROOT / self.cfg["output"]["dir"] / self.exp / method_dir(method) / self.tier

    def begin(self, method: str) -> bool:
        """Start one method's run. False = already done (metrics.json exists) and not forced: skip it."""
        d = self.path(method)
        if (d / "metrics.json").exists() and not self.force:
            self.log.info(f"{self.exp} {method}: done already ({show(d)}); --force to re-run")
            return False
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        self.method, self.dir, self._rows, self._keys = method, d, [], []
        self._handler = add_file(d / "run.log")
        self._t0 = time.time()
        self.info = {
            "experiment": self.exp,
            "method": method,
            "tier": self.tier,
            "seed": self.cfg["meta"]["seed"],
            "git_commit": self._git["commit"],
            "git_dirty": self._git["dirty"],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": self._env,
            "dataset_ids": [],
            "notes": [],
        }
        dump(self.cfg, d / "config_resolved.yaml")
        self.log.info(f"{self.exp} {method} tier={self.tier} -> {show(d)}")
        return True

    def dataset(self, dataset_id: str):
        if dataset_id not in self.info["dataset_ids"]:
            self.info["dataset_ids"].append(dataset_id)

    def note(self, msg: str):
        """A run-level fact a reader of rows.csv must know (saturation, skipped points, backend caveats)."""
        self.log.warning(msg)
        self.info["notes"].append(msg)

    def row(self, **r):
        for k in r:
            if k not in self._keys:
                self._keys.append(k)
        self._rows.append(r)

    def end(self):
        with open(self.dir / "rows.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self._keys)
            w.writeheader()
            w.writerows(self._rows)
        self.info.update(
            finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            runtime_s=round(time.time() - self._t0, 1),
            rows=len(self._rows),
        )
        (self.dir / "run_info.json").write_text(json.dumps(self.info, indent=2, default=str))
        summary = summarize(self.exp, self._rows, self.cfg)
        (self.dir / "metrics.json").write_text(json.dumps(summary, indent=2, default=str))  # last: marks done
        self.log.info(f"{self.exp} {self.method}: {len(self._rows)} rows in {self.info['runtime_s']} s")
        remove(self._handler)
        self.method = None
