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
make smoke                              # every experiment, tiny sizes (plumbing check only)
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
| Fig. 7 blockchain finalization overhead | `make eval EXP=exp01_redaction_throughput` (the figure counts each point's anchoring, #9) and `make eval EXP=exp05_blockchain_overhead` (text table), then `make figures` | `Result/Pdf/exp5_blockchain_overhead.pdf` |
| Each baseline's own published figures | `make paper-runs` | `Benchmark/results/reproduction/<S id>/*.csv` |

A finished (experiment, method, tier) is skipped on re-run; `make eval ... FORCE=--force` re-runs it.
The experiment tier refuses to run without Besu and the liboqs ML-DSA-65 backend.

**The paper's full run** is split over AWS workers in us-east-2, one machine per experiment and run (hybrid plan:
Exp. 2–5 in 3 runs, Exp. 0 and 1 once); see [Results](#results-full-run-of-3-nov-2026) and `Other/docs/aws-runbook.md`.
Every AWS action needs the agent's owner's yes for that action, logged on its issue (`CLAUDE.md`):

```bash
Benchmark/deploy/aws/build_image.sh                       # prebuilt worker image of the committed code
Benchmark/deploy/aws/provision_workers.sh 13              # 13 on-demand m7i.4xlarge workers
Benchmark/deploy/aws/launch_reps.sh 3                     # prover (c8g.48xlarge) first, then every part, detached
Benchmark/deploy/aws/collect_reps.sh 3                    # results -> veredact-bench: coverage, aggregation, tables, figures
Benchmark/deploy/aws/teardown_workers.sh                  # workers, provers and the image
```

## Hardware

| Role | Machine |
|:--|:--|
| Each experiment (all its systems) | AWS EC2 m7i.4xlarge (16 vCPU Xeon 8488C, 64 GiB), Ubuntu 24.04, us-east-2, 7-validator Besu QBFT on the same host |
| VeRedact-PQ's requesters (Exp. 1) | one c8g.48xlarge prover host (192 Graviton4 cores) |
| Tests, smoke, collection, figures | `veredact-bench` (r7i.4xlarge, ap-southeast-1) |

## Layout

```
VeRedact/
├── README.md  CLAUDE.md  AUDIT_LOG.md    overview + results, team/agent rules, audit findings
├── .github/                              issue/PR templates, CI (pytest + ruff), CODEOWNERS, setup-repo.sh
├── Overleaf/                             the manuscript
│   ├── VeRedact-optimize.tex             manuscript (changes via PR)
│   └── tables/                           generated table: tab_primitives.tex (after the run)
├── Result/                               generated figures only (after the run)
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
│   ├── deploy/                           aws/ (laptop side: server, workers, provers, split run), server/
│   │                                     (bootstrap, watchdogs), besu/ (QBFT network), experiments/ (runners)
│   └── results/                          raw runs <experiment>/<method>/<tier>/ (gitignored)
├── Reference/                            papers: PDF, Markdown full text, summary, figures
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

## Results: full run of 9–10 Nov 2026

| Item | Value |
|:--|:--|
| Code / image | Exp. 0, 2–5: `Benchmark/` of commit `6be9e38`, image `ami-08e910433d99b0dda`; Exp. 1: commit `0afabd3`, image `ami-0488a53cf0e92d022` (`Benchmark/` differs from `6be9e38` only by #30, a test skipped on the arm64 prover). Every image build ran the full test suite |
| Systems | Exp. 1: VeRedact-PQ, Refs. [1], [13], [27], [34] (ablation variants dropped in #5); Exp. 4 adds Ref. [13] per block |
| Scale | 10^5-transaction ledger, n_Q up to 10^4; Exp. 1 at 25–1,000 req/s with 20 % invalid requests |
| Repetitions | Exp. 2–5: 3 runs × 10 samples per point (S13 at n_Q = 10^4 in Exp. 3: 3 × 2), seeds 20260929 + (r−1)·1000; Exp. 0, 1: run 1 only (Exp. 1 error bars from 6 × 10-s sub-windows and bootstrap) |
| When | Exp. 0, 2–5: 9 Nov 2026, 17:46–23:20 UTC. Exp. 1 (10 Nov, same worker): baselines 03:31–05:28 UTC, VeRedact-PQ 06:06–06:28 UTC |
| Coverage | `check_coverage.py --tier experiment`: 477/477, 387/387, 387/387 (runs 1–3); every part `EXIT=0` |

Where: figures in `Result/`, table in `Overleaf/tables/tab_primitives.tex` (both committed); combined numbers
`Benchmark/results/<exp>/<method>/experiment-reps/metrics.json`, per run `experiment-repNN/` (gitignored, on
veredact-bench `/opt/veredact/Benchmark/results/`; aggregates in the GitHub release `run-2026-11-10`). In
`experiment-reps`, `median` is the mean of the per-run medians, `ci95_halfwidth` Student's t over 3 runs, `p95`
pooled over runs. Regenerate: `VRPQ_RESULTS_TIER=experiment-reps make tables figures TIER=experiment`.

Caveats a reader must know: Exp. 1 did not run on 9 Nov (the arm64 prover failed its set-up test, fixed in #30)
and ran on 10 Nov on a new worker 1 in us-east-2c, next to the prover. There it ran in two steps on the same
machine: the four baselines first, then VeRedact-PQ alone after the worker had stopped (~40 min later). VeRedact-PQ's
first attempt (03:27 UTC) aborted before measuring (prover port blocked by a stale security-group rule, fixed in
#31) and its folder was rerun whole. "Missed by the block watcher" receipts (Exp. 1 baselines, Exp. 3 run 1) were
all found by hash lookup. Exp. 1 is one run (within-run error bars); smoke numbers are never results.

Status and open work: GitHub issues, on the board https://github.com/users/Ppdfd/projects/1. Older history: git log (`TASK.md` and `HANDOFF.md` until 6 Nov 2026).
