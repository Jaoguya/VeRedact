# VeRedact-PQ — evaluation code

**Scalable Post-Quantum Redaction with Multi-Party Authorization and Verifiable Auditing**
(SIIT, Thammasat University). Every table and figure in the manuscript traces to one config, one script
run and one results folder: see [`paper/MANIFEST.md`](paper/MANIFEST.md).

## Reproduce

Everything runs on the AWS server (`veredact-bench`), never on the laptop: on the laptop every `make` target is
forwarded by `deploy/aws/remote.sh`, which starts the instance if needed, syncs the sources, runs the target
there and copies `paper/` back. Any other command: `deploy/aws/remote.sh '<command>'`.

```bash
make test lint                          # tests, ruff gate (on the server)
make smoke                              # every experiment, tiny sizes, in-process ledger (server, ~10 min)
make all TIER=experiment                # the paper: all experiments + tables + figures (server, see below)
make tables figures TIER=experiment     # regenerate paper/tables and paper/figures from the server's results/
```

One command per paper artifact (`TIER=experiment` for the paper's numbers):

| Paper item | Command | Output |
|:--|:--|:--|
| Table: primitive timings | `make eval EXP=exp00_primitives` then `make tables` | `paper/tables/tab_primitives.tex` |
| Fig. 3 redaction latency / throughput | `make eval EXP=exp01_redaction_throughput` then `make figures` | `paper/figures/exp1_redaction_throughput.pdf` |
| Fig. 4 authorization latency | `make eval EXP=exp02_authorization_latency` then `make figures` | `paper/figures/exp2_authorization_latency.pdf` |
| Fig. 5 audit efficiency | `make eval EXP=exp03_audit_efficiency` then `make figures` | `paper/figures/exp3_audit_efficiency.pdf` |
| Fig. 6 verification time | `make eval EXP=exp04_verification_time` then `make figures` | `paper/figures/exp4_verification_time.pdf` |
| Fig. 7 gas, table: gas per operation | `make eval EXP=exp05_gas_consumption` then `make tables figures` | `paper/figures/exp5_gas_consumption.pdf`, `paper/tables/tab_gas.tex` |
| Each baseline's own published figures | `make paper-runs` | `results/reproduction/<S id>/*.csv` |

A finished (experiment, method, tier) is skipped on re-run; `make eval ... FORCE=--force` re-runs it.
The experiment tier refuses to run without Besu and the liboqs ML-DSA-65 backend, so it runs on the server:

```bash
deploy/aws/provision_ec2.sh                     # once: EC2 instance, bootstrap (liboqs, Rust, venv, tests)
deploy/aws/launch_run.sh smoke                  # first run on Besu
deploy/aws/launch_run.sh pilot                  # sets the [CONFIRM] values that need measurements
deploy/aws/launch_run.sh experiment             # the paper's run (detached; idle watchdog powers off)
deploy/aws/fetch_results.sh                     # copies results/ and paper/ back
deploy/aws/teardown_ec2.sh
```

## Hardware and runtime

| Tier | Machine | Ledger | Runtime |
|:--|:--|:--|:--|
| smoke | AWS EC2 c7i.4xlarge (the same server) | in-process | ~10 min |
| pilot | AWS EC2 c7i.4xlarge (16 vCPU, 32 GiB), Ubuntu 24.04, ap-southeast-1 | 7-validator Besu QBFT | ~3–5 h |
| experiment | same instance | same | ~2–4 h (one run per point; Exp. 1 dominates) |

Per experiment on the experiment tier (estimate, to be replaced by `run_info.json` runtimes after the run):
exp00 minutes · exp01 ~1.5–2.5 h · exp02 ~0.5 h · exp03 + exp04 ~0.5–1 h · exp05 ~0.5 h.

## Layout

| Folder | Contents |
|:--|:--|
| `configs/` | `base.yaml` (shared), `datasets/`, `methods/` (VeRedact-PQ + 4 baselines), `experiments/` (one per paper experiment), `tiers/` (smoke / pilot / experiment scale), `aws.toml` (server) |
| `src/veredact_bench/` | `data/` · `methods/` (one `Scheme` interface: VeRedact-PQ and the baselines) · `metrics/` (pure, tested) · `evaluation/` (runners, results writer, ledger backends) · `reporting/` (tables, figures) · `utils/` (config, seed, logging, validation) |
| `native/pqzk_stark/` | Rust winterfell STARK for the PQZK policy relation |
| `contracts/` | Solidity contracts anchored on Besu |
| `scripts/` | thin entry points: `run_eval.py`, `make_tables.py`, `make_figures.py`, `validate_config.py`, `capabilities.py`, `paper_reproduction.py` |
| `results/` | raw outputs `results/<experiment>/<method>/<tier>/` (gitignored) |
| `paper/` | generated `tables/*.tex`, `figures/*.pdf`, and `MANIFEST.md` |
| `tests/` | metrics, config gating, results layout, fidelity of every method, baseline constructions, a tiny end-to-end run |
| `data/` | README only: the dataset is generated from the seed |
| `deploy/` | AWS provisioning + launch + idle watchdog, server bootstrap, Besu QBFT network, tier runner |
| `Scheme/` | the four baseline papers (PDF, full text, summary) |
| `overleaf/` | final manuscript `VeRedact-2.tex` (never edited here), generated `VeRedact.md`, `newchange.md` (text changes still to paste) |
| `docs/` | `experiments.md` (rules, boundaries), `baselines/*.md`, `paper-conformance.md`, `aws-runbook.md` |
| `tools/` | PDF→Markdown and TeX→Markdown converters |

Status and open decisions: [`TASK.md`](TASK.md).
