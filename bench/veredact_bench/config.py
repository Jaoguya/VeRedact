"""Default parameters (paper Table VII) and per-experiment sweeps (Sec. Performance Analysis).

Values the paper still marks [TBD] or in brackets are provisional here too — change them in one place.
"""
from dataclasses import dataclass, field


@dataclass
class Defaults:
    n: int = 7                     # committee size            [7]
    t: int = 5                     # threshold                 [5]
    B_min: int = 8                 # ABRRR lower bound         [8]
    B_max: int = 256               # ABRRR upper bound         [256]
    T_max_ms: float = 500.0        # max waiting time          [500] ms
    N: int = 256                   # leaves per tx batch       [256]
    S: int = 16                    # SA-RLI shards             [16]
    S_A: int = 16                  # RAI shards                [16]
    ledger_size: int = 100_000     # transactions              [1e5]
    zipf_s: float = 0.8            # target skew               [0.8]
    payload_min: int = 256         # bytes
    payload_max: int = 4096        # bytes
    repetitions: int = 30          # runs, 95% CI
    # --- values the paper leaves [TBD]; set once measured / decided -------------------------------
    block_period_s: float = 2.0    # Besu QBFT block period ([TBD]-validator network)
    net_latency_ms: float = 10.0   # tc netem inter-node latency [TBD]
    vps_workers: int = 4           # parallel VPS validation workers
    ch_dim: int = 256              # PQCH stand-in dimension
    zk_prove_ms: float = 0.0       # requester-side, excluded from T_val (set >0 to model it)
    zk_verify_ms: float = 5.0      # STARK verify [TBD: library]
    zk_proof_bytes: int = 80_000   # |pi| [TBD: library]
    policy_ms: float = 4.0         # T_Pol stand-in for policy-based CH authorization (baselines)


D = Defaults()

EXP1 = dict(
    rates=[100, 250, 500, 1000, 2000, 5000],       # [100] .. [5,000] req/s
    zipf=[0.0, 0.4, 0.8, 1.2],
    zipf_rate=1000,                                 # fixed rate for the skew sweep
    fixed_batch=64,                                 # Fixed-Batch variant [64]
    duration_s=10.0,
    bursty=dict(on_s=2.0, off_s=2.0, peak_factor=4.0),
)

EXP2 = dict(
    committee=[4, 7, 10, 16, 32],                  # t = floor(2n/3) + 1
    batch_sizes=[1, 8, 32, 64, 128, 256],
)

EXP3 = dict(
    n_Q=[10, 100, 1_000, 10_000],
    records_per_batch=[1, 4, 16, 64],              # 1 .. [64]
)

EXP4 = dict(
    n_Q=[10, 100, 1_000, 10_000],
    levels=["normal", "deep"],
    inject=[0.01, 0.05, 0.10],                     # [1%-10%] modified/substituted/stale
)

EXP5 = dict(
    batch_sizes=[1, 8, 32, 64, 128, 256],
    zipf=[0.0, 0.8],
)


def threshold(n: int) -> int:
    return (2 * n) // 3 + 1


@dataclass
class RunConfig:
    quick: bool = False            # smaller ledger / fewer reps for smoke runs
    reps: int = D.repetitions
    ledger_size: int = D.ledger_size
    out_dir: str = "results"
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_args(cls, quick: bool, out_dir="results"):
        if quick:
            return cls(quick=True, reps=3, ledger_size=4096, out_dir=out_dir)
        return cls(out_dir=out_dir)
