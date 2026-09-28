# VeRedact-PQ benchmark harness (preparation code)

Baseline and experiment code for **VeRedact-PQ** (`overleaf/VeRedact.tex`, Sec. Evaluation).
It implements the protocol Phases 1–6, the paper's internal variants, the re-implemented baselines,
and runners for Experiments 0–5 that write CSVs and the figures referenced in the `.tex`.

> Status: **prepared, not final**. Everything runs end to end, but three primitives are
> stand-ins until the paper's [TBD] choices are made (see *Stand-ins* below). Numbers produced
> with stand-ins are for plumbing and trend checks, not for the paper.

## Quick start

```bash
cd benchmark
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                         # unit tests
.venv/bin/python -m veredact_bench exp0 --quick       # Table VI primitives
.venv/bin/python -m veredact_bench all --quick        # smoke run of every experiment
.venv/bin/python -m veredact_bench exp1 exp2          # full runs (30 reps, 1e5-tx ledger)
.venv/bin/python -m veredact_bench.plot          # results/*.csv -> plot/*.png
```

`--quick` = 4,096-tx ledger, 3 repetitions, trimmed sweeps. Full runs follow Table VII defaults.

All parameters live in `config/benchmark.toml`; every scheme's workflow lives in `config/schemes.toml`.
CSVs go to `results/`, figures to `plot/` (repository root).

## Layout

| Path | What |
|:--|:--|
| `config/benchmark.toml` | Table VII defaults + every experiment's sweep; all [TBD] values in one place |
| `config/schemes.toml` | Every scheme: manuscript ref, paper, experiments, Table IV workflow |
| `veredact_bench/config.py` | Loads `benchmark.toml` |
| `veredact_bench/crypto/` | H/H1/H2/H_A (SHA3-256), PRF (HMAC-SHA3-256), ML-DSA-65, PQZK, PQCH, classical CH; op counters named after Table III symbols |
| `veredact_bench/ds/` | Merkle tree + multiproof + BIMC update; sharded SA-RLI / RAI |
| `veredact_bench/protocol/ledger.py` | Phase 1 setup, Phase 2 RADC commitments, batches, checkpoints (shared by all schemes) |
| `veredact_bench/protocol/veredact.py` | Phases 3–6: VPS validation, ABRRR, committee auth, Algorithm 1, RAI audit |
| `veredact_bench/baselines/` | Per-request baselines built from `schemes.toml` |
| `veredact_bench/sim.py` | Discrete-event pipeline for Exp. 1 (real code, measured service times, block-period finality) |
| `veredact_bench/experiments.py` | `exp0` … `exp5` |
| `veredact_bench/gas_model.py` | Offline gas estimate from the on-chain op log |
| `contracts/VeRedactRegistry.sol` | Checkpoint/authorization/RAI anchoring + baseline per-request log |
| `scripts/measure_gas_besu.py` | Replays `results/exp5_chainlog.json` on Besu QBFT and records receipt gas |

## Experiments ↔ paper

| Exp | Figure/Table | Schemes | Sweep |
|:--|:--|:--|:--|
| 0 | Table VI | primitives | — |
| 1 | Fig. 3 | VeRedact-PQ, Per-Request, Fixed-Batch, No-BIMC, Huang [14], Wang [17], Liu [27], Xue [33] | rate 100–5,000 req/s; Zipf s ∈ {0, 0.4, 0.8, 1.2} |
| 2 | Fig. 4 | VeRedact-PQ, Re-ZK, Liu [27], Dong [15], Li [1] | n ∈ {4,7,10,16,32}, t = ⌊2n/3⌋+1; m ∈ {1,…,256} |
| 3 | Fig. 5 | VeRedact-PQ, Per-Record Evidence, EAQ-VRBC [13], Xue [33], Miao [20] | n_Q ∈ {10,…,10⁴}; records/batch 1–64 |
| 4 | Fig. 6 | same as 3, normal/deep, PQ-adapted + classical | n_Q; 1–10 % injected faults |
| 5 | Fig. 7, Table VIII | VeRedact-PQ vs Exp. 1 baselines | m ∈ {1,…,256}; s ∈ {0, 0.8} |

## Stand-ins (replace before producing paper numbers)

| Primitive | Paper | Here | Where to swap |
|:--|:--|:--|:--|
| PQSIG | ML-DSA-65 via liboqs | **real** ML-DSA-65 via `pqcrypto` (auto-uses liboqs-python if installed) | `crypto/pqsig.py` |
| PQZK | transparent STARK [TBD: library] | `SimulatedSTARK`: configurable prove/verify ms and proof size; not sound/ZK | `crypto/pqzk.py` |
| PQCH | SIS-based CH [10],[17] [TBD] | `LinearThresholdCH`: correct t-of-n PartAdapt/Combine/Reshare algebra and lattice-like cost, **not collision resistant** | `crypto/pqch.py` |
| T_Pol | ABE decryption | busy-work of `policy_ms` | `config/benchmark.toml` |

`pqcrypto`'s ML-DSA-65 signs in ~8.7 ms on this Mac (verify 0.17 ms); liboqs is expected to be much
faster, so signing-heavy results (committee auth, attestations, checkpoints) are pessimistic until
`brew install liboqs && pip install liboqs-python` (then `VRPQ_SIG_BACKEND=oqs`).

## Baselines: how grounded

Per the paper, baselines are re-implemented on the same ledger with the same PQ primitives and follow
their original per-request workflow (`config/schemes.toml`).

| Key | Ref | Grounded in |
|:--|:--|:--|
| `li2025_dch` | [1] | PDF (`Scheme/S1_ref01_Li2025_ImprovedDCH`) |
| `eaq_vrbc2025` | [13] | PDF (`Scheme/S2_ref13_Zhang2025_EAQ-VRBC`) |
| `liu2026_etch` | [27] | PDF (`Scheme/S3_ref27_Liu2026_ETCH`) |
| `huang2021`, `wang2024`, `xue2026_mainaux`, `dong2024`, `miao2026` | [14], [17], [33], [15], [20] | VeRedact Table IV rows only (**TODO-VERIFY**, no PDF in `Scheme/`) |

## Known modelling limits

- Exp. 1 runs everything in one process; the simulated clock uses measured service times with
  `vps_workers` parallel validators, one committee server and one execution server. Docker/`tc netem`
  deployment from the paper is not scripted yet.
- Exp. 5 CSV uses the **offline estimate**; paper numbers must come from `scripts/measure_gas_besu.py`.
- The audit state-transition check verifies PQCH continuity against the latest checkpoint only.
