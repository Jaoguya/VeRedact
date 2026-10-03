# VeRedact-PQ

**Scalable Post-Quantum Redaction with Multi-Party Authorization and Verifiable Auditing**
(SIIT, Thammasat University).

| Folder | Contents |
|:--|:--|
| `overleaf/` | Final manuscript `VeRedact-2.tex` (never edited here), its generated Markdown `VeRedact.md`, and `newchange.md` — text changes still to paste in Overleaf |
| `Scheme/` | Baseline papers, one folder per scheme numbered by manuscript reference: S1 = [1] Li (Improved DCH), S13 = [13] EAQ-VRBC, S27 = [27] Liu (ETCH), S34 = [34] J. Xue (REBS) |
| `config/` | `smoke.toml` / `pilot.toml` / `experiment.toml` — every experiment parameter, identical keys, one tier per scale; `schemes.toml` — scheme metadata + each paper's own evaluation parameters; `aws.toml` — server |
| `benchmark/` | Harness: VeRedact-PQ protocol (Phases 1–6), real PQ primitives (ML-DSA-65, SIS chameleon hash, winterfell STARK in `pqzk_stark/`), Scheme contract, registry, primitive-timing and Exp. 1–5 runners, contracts, tests |
| `experiment/` | One folder per baseline: its construction (`s<ref>_scheme.py`), its Scheme adapter (`s<ref>_baseline.py`), its own paper's evaluation (`s<ref>_run.py`), tests |
| `deploy/` | AWS provisioning + launch + idle watchdog, server bootstrap, Besu QBFT network, tier runner |
| `results/` | `results/<exp>/<run_id>/rows.csv` + `manifest.json`; `results/S*_*.csv` from the paper runners |
| `plot/` | Figures rendered from the newest runs, plus `primitives_table.csv` and `gas_by_operation.csv` |
| `tools/` | PDF→Markdown, TeX→Markdown and tidy scripts |
| `docs/` | `experiments.md` (rules, boundaries, systems), `baselines/*.md` (per baseline), `paper-conformance.md` (manuscript vs code), `aws-runbook.md` |

Status and open decisions: [`TASK.md`](TASK.md). File placement and workflows:
[`.claude/skills/veredact/SKILL.md`](.claude/skills/veredact/SKILL.md).

```bash
make venv build-zk test       # local setup (Python 3.12 + Rust), unit + fidelity tests
make smoke                    # primitives + every experiment on config/smoke.toml (laptop, in-process ledger)
make primitives               # primitive timings only (manuscript tab:primitives)
make capabilities plots       # capability matrix from the code; figures from the newest runs
make paper-runs               # each baseline's own paper evaluation (quick)
```

Server (costs money): `deploy/aws/provision_ec2.sh` once, then `deploy/aws/launch_run.sh smoke`, `pilot` and,
after the pilot, `deploy/aws/launch_run.sh experiment` — see `docs/aws-runbook.md` and the tracker in `TASK.md`.
