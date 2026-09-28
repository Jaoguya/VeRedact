"""Result writer: one row per request (never pre-aggregated) + a run manifest.

Every run directory results/<exp>/<run_id>/ holds
  rows.csv         raw per-request / per-operation measurements
  manifest.json    resolved config, seed, dataset id, git commit, environment fingerprint, timestamps
A result missing any manifest field is not publishable (docs/experiments.md §6).
"""
import csv
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from .config import REPO_ROOT


def _git(*args):
    try:
        return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return "unavailable"


def environment_fingerprint() -> dict:
    fp = {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
          "cpu_count": os.cpu_count()}
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                fp["cpu"] = line.split(":", 1)[1].strip()
                break
        fp["mem_gb"] = round(int(open("/proc/meminfo").readline().split()[1]) / 1048576, 1)
    except OSError:
        fp["cpu"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                   text=True).stdout.strip() or platform.processor()
    try:
        from .crypto.pqsig import load_pqsig
        fp["signature_backend"] = load_pqsig().name
    except Exception as e:  # recorded, not hidden
        fp["signature_backend"] = f"unavailable: {e}"
    return fp


class RunWriter:
    def __init__(self, cfg: dict, experiment: str, config_path: str):
        self.run_id = time.strftime("%Y%m%d-%H%M%S")
        self.dir = REPO_ROOT / cfg["output"]["dir"] / experiment / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._rows, self._keys = [], []
        self.manifest = {
            "experiment": experiment,
            "run_id": self.run_id,
            "config_path": config_path,
            "resolved_config": cfg,
            "seed": cfg["meta"]["seed"],
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "environment": environment_fingerprint(),
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dataset_ids": [],
            "notes": [],
        }

    def dataset(self, dataset_id: str):
        if dataset_id not in self.manifest["dataset_ids"]:
            self.manifest["dataset_ids"].append(dataset_id)

    def note(self, msg: str):
        """A run-level fact a reader of rows.csv must know (saturation, skipped points, backend caveats)."""
        print(f"  note: {msg}", flush=True)
        self.manifest["notes"].append(msg)

    def row(self, **r):
        for k in r:
            if k not in self._keys:
                self._keys.append(k)
        self._rows.append(r)

    def close(self):
        with open(self.dir / "rows.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self._keys)
            w.writeheader()
            w.writerows(self._rows)
        self.manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.manifest["rows"] = len(self._rows)
        (self.dir / "manifest.json").write_text(json.dumps(self.manifest, indent=2, default=str))
        print(f"-> {self.dir.relative_to(REPO_ROOT)} ({len(self._rows)} rows)")
        return self.dir
