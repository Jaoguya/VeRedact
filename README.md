# VeRedact-PQ

**Scalable Post-Quantum Redaction with Multi-Party Authorization and Verifiable Auditing**
(SIIT, Thammasat University).

| Folder | Contents |
|:--|:--|
| `overleaf/` | Manuscript `VeRedact.tex` and its generated Markdown `VeRedact.md` |
| `Scheme/` | Papers used in the evaluation, one folder per scheme, numbered by manuscript reference: S1 = [1] Li (Improved DCH), S2 = [13] EAQ-VRBC, S3 = [27] Liu (ETCH), S4 = [34] J. Xue (REBS) |
| `config/` | `schemes.toml` — every scheme (ref, paper, experiments, workflow); `benchmark.toml` — all benchmark parameters |
| `benchmark/` | Evaluation harness for Experiments 0–5 (protocol, baselines, simulator, contracts, tests) |
| `results/` | Benchmark CSV output |
| `plot/` | Figures rendered from `results/` |
| `tools/` | PDF→Markdown, TeX→Markdown and tidy scripts |
| `docs/` | `benchmark.md` (how to run, stand-ins, limits), `capability-matrix.md` (scheme × experiment) |

Where each kind of file goes and the step-by-step workflows are in
[`.claude/skills/veredact/SKILL.md`](.claude/skills/veredact/SKILL.md).

Quick start:

```bash
python3 tools/tex2md.py overleaf/VeRedact.tex overleaf/VeRedact.md    # sync manuscript Markdown
cd benchmark && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m veredact_bench all --quick && .venv/bin/python -m veredact_bench.plot
```
