# VeRedact-PQ — evaluation code

**Scalable Post-Quantum Redaction with Multi-Party Authorization and Verifiable Auditing**
(SIIT, Thammasat University). Every table and figure in the manuscript traces to one config, one script
run and one results folder: see [`Other/docs/paper-manifest.md`](Other/docs/paper-manifest.md).

## Reproduce

Everything runs on the AWS server (`veredact-bench`), never on the laptop: on the laptop every `make` target is
forwarded by `Benchmark/deploy/aws/remote.sh`, which starts the instance if needed, syncs the sources, runs the target
there and copies `Result/` back. Any other command: `Benchmark/deploy/aws/remote.sh '<command>'`.

```bash
cd Benchmark
make test lint                          # tests, ruff gate (on the server)
make smoke                              # every experiment, tiny sizes, in-process ledger (server, ~10 min)
make all TIER=experiment                # the paper: all experiments + tables + figures (server, see below)
make tables figures TIER=experiment     # regenerate Overleaf/tables and Result/ from the server's Benchmark/results/
```

One command per paper artifact (`TIER=experiment` for the paper's numbers):

| Paper item | Command | Output |
|:--|:--|:--|
| Table: primitive timings | `make eval EXP=exp00_primitives` then `make tables` | `Overleaf/tables/tab_primitives.tex` |
| Fig. 3 redaction latency / throughput | `make eval EXP=exp01_redaction_throughput` then `make figures` | `Result/Pdf/exp1_redaction_throughput.pdf` |
| Fig. 4 authorization latency | `make eval EXP=exp02_authorization_latency` then `make figures` | `Result/Pdf/exp2_authorization_latency.pdf` |
| Fig. 5 audit efficiency | `make eval EXP=exp03_audit_efficiency` then `make figures` | `Result/Pdf/exp3_audit_efficiency.pdf` |
| Fig. 6 verification time | `make eval EXP=exp04_verification_time` then `make figures` | `Result/Pdf/exp4_verification_time.pdf` |
| Fig. 7 gas, table: gas per operation | `make eval EXP=exp05_gas_consumption` then `make tables figures` | `Result/Pdf/exp5_gas_consumption.pdf`, `Overleaf/tables/tab_gas.tex` |
| Each baseline's own published figures | `make paper-runs` | `Benchmark/results/reproduction/<S id>/*.csv` |

A finished (experiment, method, tier) is skipped on re-run; `make eval ... FORCE=--force` re-runs it.
The experiment tier refuses to run without Besu and the liboqs ML-DSA-65 backend, so it runs on the server:

```bash
Benchmark/deploy/aws/provision_ec2.sh                     # once: EC2 instance, bootstrap (liboqs, Rust, venv, tests)
Benchmark/deploy/aws/launch_run.sh smoke                  # first run on Besu
Benchmark/deploy/aws/launch_run.sh pilot                  # sets the [CONFIRM] values that need measurements
Benchmark/deploy/aws/launch_run.sh experiment             # the paper's run (detached; idle watchdog powers off)
Benchmark/deploy/aws/fetch_results.sh                     # copies Benchmark/results/ and Result/ back
Benchmark/deploy/aws/teardown_ec2.sh
```

## Hardware and runtime

| Tier | Machine | Ledger | Runtime |
|:--|:--|:--|:--|
| smoke | AWS EC2 c7i.4xlarge (the same server) | in-process | ~10 min |
| pilot | AWS EC2 c7i.4xlarge (16 vCPU, 32 GiB), Ubuntu 24.04, ap-southeast-1 | 7-validator Besu QBFT | ~3–5 h |
| experiment | same instance + 2 × c7i.48xlarge prover hosts (Exp. 1, VeRedact-PQ) | same | ~9 h measured (2026-10-09 run, excluding a 3.5 h hang) |

Per-experiment runtimes of the 2026-10-09 run: `Benchmark/results/<exp>/<method>/experiment/run_info.json`.

## Layout

```
VeRedact/
├── README.md  TASK.md  AUDIT_LOG.md      overview, status and open decisions, audit findings
├── Overleaf/                             the manuscript
│   ├── VeRedact-2.tex                    final manuscript (never edited here); VeRedact.md generated from it
│   ├── newchange.md                      text changes still to paste
│   ├── revised/                          marked-up copies (red / blue) + their PDFs
│   └── tables/                           generated tables: tab_primitives.tex, tab_gas.tex
├── Result/                               generated figures only
│   ├── Pdf/                              exp1..exp5_*.pdf (vector, for the paper)
│   └── Picture/                          exp1..exp5_*.png
├── Benchmark/                            the experiment code (the server runs everything from here)
│   ├── Makefile  pyproject.toml
│   ├── configs/                          base.yaml, datasets/, methods/, experiments/, tiers/, aws.toml
│   ├── src/veredact_bench/               data/, methods/ (VeRedact-PQ + 4 baselines + LETA), metrics/, evaluation/,
│   │                                     reporting/, utils/
│   ├── native/pqzk_stark/                Rust winterfell STARK (PQZK policy relation)
│   ├── contracts/                        Solidity contracts anchored on Besu
│   ├── scripts/                          entry points: run_eval.py, make_tables.py, make_figures.py, ...
│   ├── tests/                            metrics, config gating, results layout, fidelity, end-to-end
│   ├── deploy/                           aws/ (laptop side), server/ (bootstrap, watchdogs, provers),
│   │                                     besu/ (QBFT network), experiments/ (tier runner, full run)
│   └── results/                          raw runs <experiment>/<method>/<tier>/ (gitignored)
├── Reference/                            papers: PDF, LaTeX/Markdown full text, summary, figures
│   ├── S1_Li2025_ImprovedDCH/  S13_Zhang2025_EAQ-VRBC/  S27_Liu2026_ETCH/  S34_Xue2025_REBS/  S99_Li2026_LETA/
│   └── zkredact/                         ZK-Redact journal version (writing-style reference)
└── Other/
    ├── docs/                             experiments.md, baselines/*.md, paper-conformance.md,
    │                                     aws-runbook.md, paper-manifest.md
    ├── tools/                            PDF -> Markdown and TeX -> Markdown converters
    └── data/                             README only: the dataset is generated from the seed
```

On the server the same layout lives under `/opt/veredact` (`Benchmark/` is synced there; `Result/` and
`Overleaf/tables/` are generated there and copied back).

Status and open decisions: [`TASK.md`](TASK.md).
