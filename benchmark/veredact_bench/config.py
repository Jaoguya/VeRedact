"""Benchmark parameters, loaded from the repository-wide config/benchmark.toml (single source of truth)."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"

with open(CONFIG_DIR / "benchmark.toml", "rb") as _f:
    _CFG = tomllib.load(_f)


@dataclass(frozen=True)
class Defaults:
    n: int
    t: int
    B_min: int
    B_max: int
    T_max_ms: float
    N: int
    S: int
    S_A: int
    ledger_size: int
    zipf_s: float
    payload_min: int
    payload_max: int
    repetitions: int
    block_period_s: float
    net_latency_ms: float
    vps_workers: int
    ch_dim: int
    zk_prove_ms: float
    zk_verify_ms: float
    zk_proof_bytes: int
    policy_ms: float


D = Defaults(**_CFG["defaults"], **_CFG["tbd"])
EXP1, EXP2, EXP3, EXP4, EXP5 = (_CFG[f"exp{i}"] for i in range(1, 6))
RESULTS_DIR = str(REPO_ROOT / _CFG["paths"]["results"])
PLOTS_DIR = str(REPO_ROOT / _CFG["paths"]["plots"])


def threshold(n: int) -> int:
    return (2 * n) // 3 + 1


@dataclass
class RunConfig:
    quick: bool = False            # smaller ledger / fewer reps for smoke runs
    reps: int = D.repetitions
    ledger_size: int = D.ledger_size
    out_dir: str = RESULTS_DIR
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_args(cls, quick: bool, out_dir=RESULTS_DIR):
        if quick:
            return cls(quick=True, reps=3, ledger_size=4096, out_dir=out_dir)
        return cls(out_dir=out_dir)
