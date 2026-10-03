---
name: veredact
description: Repository conventions for the VeRedact-PQ paper project — where every file lands (scheme PDFs, converted full texts, summaries, manuscript, evaluation code in src/, baseline implementations, YAML configs, results, generated paper tables/figures), how files are named so nothing collides, the evaluation rules (real execution, no hardcoded values, one config), and the workflows for adding a scheme or baseline, syncing the manuscript .md from the .tex, and running experiments. Use whenever adding, converting, moving, or generating files in this repo.
---

# VeRedact repository skill

## 1. Layout (IEEE evaluation-code structure, adopted 2026-10-03)

```
VeRedact/
├── README.md                     the ONLY README: one command per paper table / figure, hardware, runtime
├── TASK.md                       progress tracker + run ledger (which run is current, where it is stored)
├── pyproject.toml                pinned dependencies; package in src/
├── Makefile                      venv build-zk test lint validate eval smoke pilot experiment tables figures all paper-runs
├── .claude/skills/veredact/SKILL.md   this file (the only SKILL.md)
├── configs/                      ALL parameters (YAML, OmegaConf); every value carries a marker
│   ├── base.yaml                 seed, security, environment, ledger, workload, output
│   ├── datasets/synthetic_ledger.yaml
│   ├── methods/<method>.yaml     veredact.yaml, s01_improved_dch.yaml, s13_eaq_vrbc.yaml, s27_etch.yaml, s34_rebs.yaml
│   │                             (paper metadata, comparison parameters, own-evaluation `reproduction`)
│   ├── experiments/expNN_<name>.yaml   one per paper experiment, manuscript order (exp00_primitives … exp05_gas_consumption)
│   ├── tiers/{smoke,pilot,experiment}.yaml   scale overrides only (may override existing keys only)
│   └── aws.toml                  server, Besu image/key, S3, idle shutdown (no credentials; stdlib-readable)
├── src/veredact_bench/
│   ├── data/                     dataset.py (seeded ledger + request trace)
│   ├── methods/                  scheme.py (the one interface), registry.py,
│   │   ├── veredact/             crypto/ ds/ protocol/ (Phases 1-6)
│   │   └── baselines/<method>/   construction.py, adapter.py (Scheme), reproduce.py (paper's own figures)
│   ├── metrics/                  pure functions, unit-tested
│   ├── evaluation/               runner.py, results.py, summaries.py, anchor.py, common.py, experiments/expNN_*.py
│   ├── reporting/                tables.py, figures.py, style.py, load.py
│   └── utils/                    config.py, seed.py, log.py, validate.py
├── native/pqzk_stark/            Rust crate (winterfell) -> Python module vrpq_stark
├── contracts/                    VeRedactRegistry.sol + BaselineRedactionLog
├── scripts/                      thin CLIs: run_eval.py make_tables.py make_figures.py validate_config.py capabilities.py paper_reproduction.py
├── tests/                        test_<topic>.py; baselines/test_<method>.py; fidelity in test_fidelity.py
├── results/                      <experiment>/<method>/<tier>/{rows.csv,metrics.json,config_resolved.yaml,run_info.json,run.log};
│                                 reproduction/<S id>/*.csv  (gitignored)
├── paper/                        tables/*.tex, figures/*.pdf (+ .png), MANIFEST.md — generated, never hand-edited
├── data/README.md                the dataset is generated from the seed; nothing downloaded
├── overleaf/
│   ├── VeRedact-2.tex            manuscript source — FINAL (edited only in Overleaf, never here)
│   ├── newchange.md              text changes the manuscript still needs (line, find, paste-ready replacement)
│   └── VeRedact.md               generated from the .tex — never hand-edit
├── Scheme/
│   └── S<ref>_<Author><Year>_<Short>/   one folder per paper we hold
│       ├── <original paper title>.pdf
│       ├── S<ref>_fulltext.md              marker full text (LaTeX math/tables)
│       ├── S<ref>_fulltext_pdftotext.md    plain-text fallback
│       ├── S<ref>_summary.md               structured summary
│       └── S<ref>_figures/                 figures extracted from the PDF
├── deploy/
│   ├── aws/                      provision_ec2.sh launch_run.sh refresh_ssh_rule.sh fetch_results.sh teardown_ec2.sh aws_config.py
│   ├── server/                   bootstrap_server.sh idle_watchdog.sh
│   ├── besu/                     start/stop_besu_network.sh (QBFT validators + tc netem)
│   └── experiments/              run_experiments.sh <tier> [experiment ids | all]
├── tools/                        conversion scripts (pdf->md, tex->md, marker, tidy)
└── docs/                         experiments.md, baselines/S<ref>-<short>.md, paper-conformance.md, aws-runbook.md
```

## 2. Where each file lands

| File | Destination | Name |
|:--|:--|:--|
| New scheme / baseline paper PDF | `Scheme/S<ref>_<Author><Year>_<Short>/` | keep the original PDF file name |
| Its marker full text | same folder | `S<ref>_fulltext.md` |
| Its pdftotext fallback | same folder | `S<ref>_fulltext_pdftotext.md` |
| Its structured summary | same folder | `S<ref>_summary.md` |
| Its extracted figures | `…/S<ref>_figures/` | `S<ref>_page_<p>_<Kind>_<k>.jpeg` |
| Its metadata, comparison and own-evaluation parameters | `configs/methods/` | `s<ref:02d>_<short>.yaml` (`schemes.S<ref>`, `baselines.S<ref>`, `reproduction`) |
| Its implementation | `src/veredact_bench/methods/baselines/s<ref:02d>_<short>/` | `construction.py`, `adapter.py` (Scheme), `reproduce.py` |
| Its tests | `tests/baselines/` | `test_s<ref:02d>_<short>.py` + a case in `tests/test_fidelity.py` |
| Its boundaries / deviations / fidelity checklist | `docs/baselines/` | `S<ref>-<short>.md` |
| Manuscript source | `overleaf/VeRedact-2.tex` | final — never edited in the repo |
| Manuscript text changes | `overleaf/newchange.md` | minimal find/replace items with line numbers, replacement ready to paste |
| Manuscript Markdown | `overleaf/VeRedact.md` | generated by `tools/tex2md.py` |
| Manuscript figures (system model, Merkle, etc.) | `overleaf/` next to the .tex | names used in `\includegraphics` |
| Parameter change | the YAML that owns the key (`configs/base.yaml`, `datasets/`, `methods/`, `experiments/`); scale-only differences in `configs/tiers/` | marker + rationale; never a literal or `cfg.get(k, default)` in code |
| New paper experiment | `configs/experiments/expNN_<name>.yaml` + `src/veredact_bench/evaluation/experiments/expNN_<name>.py` (`run(cfg, out)`) + `summaries.py` entry + `paper/MANIFEST.md` row | NN = manuscript order |
| Metric | `src/veredact_bench/metrics/` | pure function + test in `tests/test_metrics.py` against a hand-computed value |
| Tests | `tests/` | `test_<topic>.py` |
| Solidity contracts | `contracts/` | `<Name>.sol` |
| Cloud provisioning (AWS CLI) | `deploy/aws/` | verb-first, `*_ec2.sh` |
| Server setup | `deploy/server/` | `bootstrap_server.sh` |
| Blockchain network scripts | `deploy/besu/` | `start_/stop_besu_network.sh` |
| Experiment start script (server) | `deploy/experiments/run_experiments.sh` | one script, tier + experiments as arguments |
| Server / network settings | `configs/aws.toml` | never put credentials in the repo |
| Generated deploy state | `deploy/aws/.instance`, `deploy/besu/.network/` | gitignored |
| Experiment output | `results/<experiment>/<method>/<tier>/` | written by `RunWriter`; skipped when `metrics.json` exists unless `--force` |
| Paper tables / figures | `paper/tables/`, `paper/figures/` | `make tables figures TIER=…`; figure names = the .tex `\includegraphics` names |
| Conversion / maintenance scripts | `tools/` | verb or pipeline name, e.g. `tex2md.py` |
| Documentation | `docs/` | `<topic>.md` — never `README.md` |
| Scratch / temporary files | outside the repo (scratchpad) | — |

Placement rules:
- **No colliding names.** Exactly one `README.md` (root) and one `SKILL.md` (here). Per-scheme files carry
  the `S<ref>_` prefix so no two files in the repo share a name.
- **Scheme id = manuscript reference number**: S1 = [1], S13 = [13], S27 = [27], S34 = [34]. A new paper
  for `\bibitem{ref17}` becomes `S17` in folder `Scheme/S17_<Author><Year>_<Short>/`. If the bibliography
  is renumbered, rename the folder, its `S<ref>_` file prefixes and figure names, and the
  `configs/methods/` entry.
- Only papers we hold are baselines. A baseline is never modelled from a table row: no PDF, no baseline.
- Don't keep duplicate PDFs: before adding one, compare `shasum -a 256` with the PDFs already in `Scheme/`.
- Generated files (`overleaf/VeRedact.md`, `results/*`, `paper/tables/*`, `paper/figures/*`) are outputs —
  regenerate, don't hand-edit. Scripts stay thin: logic lives in `src/`.

## 3. Workflows

### 3.1 Add a scheme paper
1. Check it isn't already present (hash compare) and find its `\bibitem{refNN}` in `overleaf/VeRedact-2.tex`.
2. Convert (LaTeX math and tables; ~25–30 min per 10 pages):
   `tools/marker_convert.sh <paper.pdf> Scheme/S<ref>_<Author><Year>_<Short> S<ref>`
   Fast fallback without math: `python3 tools/pdf2md_pdftotext.py <pdf_dir> <out_dir>`.
3. Audit the output: every section present, word count close to the pdftotext version, and every
   algorithm/table checked against the PDF. Marker's model sometimes garbles algorithms and tables;
   re-type those from the page image and add a note `> … transcribed by hand from the PDF (page p)`.
4. Write `S<ref>_summary.md`: metadata table, abstract, problem, contributions, system/threat model,
   construction, security, evaluation setup + result tables, limitations relative to VeRedact-PQ.
5. Add `configs/methods/s<ref:02d>_<short>.yaml` with `schemes.S<ref>` (ref, bibliographic fields, folder,
   `implementation`, `boundaries`, `reproduction`).

### 3.1b Make it a baseline (same method as the conference artefact ZK-Redact)
1. `src/veredact_bench/methods/baselines/s<ref:02d>_<short>/construction.py`: the paper's construction at its
   own instantiation; every deviation named in the module docstring.
2. `adapter.py`: a `Scheme` subclass. Implement only what the paper defines; anything else raises
   `NotSupported`. `capabilities()` must be true to the code; `auth_cost()` counts what authorize does.
3. Register it in `methods/registry.py` (`BASELINES`) and in the `systems` lists of the experiments it enters
   (`configs/experiments/*.yaml`); parameters in `baselines.S<ref>` at 128-bit classical security.
4. `reproduce.py` reproduces the paper's own figures from `reproduction` (`scripts/paper_reproduction.py`).
5. Tests: `tests/baselines/test_s<ref:02d>_<short>.py` (construction) + a case in `tests/test_fidelity.py`.
6. `docs/baselines/S<ref>-<short>.md`: role per experiment, boundaries, deviations with bias direction,
   not implemented, fidelity checklist. Update `docs/paper-conformance.md` if Table I disagrees.

### 3.2 Manuscript: final, never edited here
The manuscript is final (2026-10-03). Never edit `overleaf/VeRedact-2.tex`; the code follows the manuscript.
When the text is wrong or stale, add an item to `overleaf/newchange.md`: line number, exact text to find,
and the replacement as ready-to-paste LaTeX — change only the wrong word or cite, never rewrite a paragraph.
When the user uploads a new export, regenerate the Markdown:
`python3 tools/tex2md.py overleaf/VeRedact-2.tex overleaf/VeRedact.md`
Revision colours: `\textcolor{purple}` / `{\color{purple}…}` = superseded (dropped);
blue / red = current (kept, colour removed). Equations are renumbered after dropping purple ones.

### 3.3 Run the experiments
```
make venv build-zk test lint               # once: Python 3.12 venv (pinned), Rust STARK module, tests, ruff
make smoke                                 # every experiment on the smoke tier
make eval EXP=exp02_authorization_latency TIER=pilot   # one experiment, one tier (config-gated)
make tables figures TIER=smoke             # paper/tables, paper/figures from results/
make capabilities paper-runs
```
One run per configuration point (no repetitions); a finished (experiment, method, tier) is skipped unless
`FORCE=--force`. After every run, record it in `TASK.md` §1.1 (run ledger). Rules, boundaries and limits:
`docs/experiments.md`; artifact mapping: `paper/MANIFEST.md`. Never run the experiment tier locally: it
requires Besu and the liboqs backend.

### 3.4 Run on AWS
`deploy/aws/provision_ec2.sh` → `deploy/aws/launch_run.sh <smoke|pilot|experiment> [exps]` (detached,
idle watchdog) → `deploy/aws/fetch_results.sh` → `deploy/aws/teardown_ec2.sh`. Every step costs money:
confirm with the user first.
Credentials come from the AWS CLI profile in `configs/aws.toml`; full runbook: `docs/aws-runbook.md`.

## 4. Environment notes
- marker lives in `~/.venvs/marker` (Python 3.12). It is locally patched so that HTML blocks with
  unclosed tags (e.g. a missing `</table>` after an algorithm) no longer swallow the rest of the paper;
  originals are kept as `*.orig` in `marker/schema/blocks/`. Balanced mode needs `brew install llama.cpp`.
- ML-DSA-65: liboqs on the server (required by the experiment tier); `pqcrypto` fallback on the laptop
  (~8.7 ms per sign — smoke numbers are plumbing checks only).
- The STARK module needs Rust (`brew install rust` / rustup) and `make build-zk`.
- The repo is public on GitHub and the scheme PDFs/full texts are IEEE-licensed to Thammasat University.
