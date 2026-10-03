# Paper artifact manifest

Every number in the manuscript (`overleaf/VeRedact-2.tex`) maps to one config, one script run and one results
folder. `<tier>` is `experiment` for the paper; `smoke` and `pilot` exist only to test the pipeline.
Regenerate everything with `make all TIER=experiment` (on the server) or, from fetched results,
`make tables figures TIER=experiment`.

| Paper item | Generated file | Script | Config | Results path |
|:--|:--|:--|:--|:--|
| Table: Execution Time of Cryptographic Primitives (`tab:primitives`) | `paper/tables/tab_primitives.tex` | `scripts/make_tables.py` | `configs/experiments/exp00_primitives.yaml` | `results/exp00_primitives/<method>/<tier>/` |
| Fig. 3 Redaction performance (`fig:exp1_redaction`) | `paper/figures/exp1_redaction_throughput.pdf` | `scripts/make_figures.py` | `configs/experiments/exp01_redaction_throughput.yaml` | `results/exp01_redaction_throughput/<method>/<tier>/` |
| Fig. 4 Authorization latency (`fig:exp2_auth`) | `paper/figures/exp2_authorization_latency.pdf` | `scripts/make_figures.py` | `configs/experiments/exp02_authorization_latency.yaml` | `results/exp02_authorization_latency/<method>/<tier>/` |
| Fig. 5 Audit efficiency (`fig:exp3_audit`) | `paper/figures/exp3_audit_efficiency.pdf` | `scripts/make_figures.py` | `configs/experiments/exp03_audit_efficiency.yaml` | `results/exp03_audit_efficiency/<method>/<tier>/` |
| Fig. 6 Verification time (`fig:exp4_verify`) | `paper/figures/exp4_verification_time.pdf` | `scripts/make_figures.py` | `configs/experiments/exp04_verification_time.yaml` | `results/exp04_verification_time/<method>/<tier>/` |
| Exp. 4 text: falsely rejected valid records | `paper/figures/exp4_granularity.pdf` | `scripts/make_figures.py` | `configs/experiments/exp04_verification_time.yaml` | `results/exp04_verification_time/<method>/<tier>/` |
| Fig. 7 Gas consumption (`fig:exp5_gas`) | `paper/figures/exp5_gas_consumption.pdf` | `scripts/make_figures.py` | `configs/experiments/exp05_gas_consumption.yaml` | `results/exp05_gas_consumption/<method>/<tier>/` |
| Table: Gas per contract operation (`tab:gas`) | `paper/tables/tab_gas.tex` | `scripts/make_tables.py` | `configs/experiments/exp05_gas_consumption.yaml` | `results/exp05_gas_consumption/veredact/<tier>/` |
| Significance of the headline comparisons (reviewer response; not in the manuscript) | `paper/tables/tab_significance.tex` | `scripts/make_tables.py` | experiments 01–04 | as above |
| Table: Default Experimental Parameters (`tab:params`) | — (values) | — | `configs/base.yaml`, `configs/datasets/synthetic_ledger.yaml`, `configs/methods/veredact.yaml` | — |
| Table I capability marks for the four baselines (`tab:comparison`) | — | `scripts/capabilities.py` | `configs/methods/*.yaml` | — (from each implementation's `capabilities()`) |
| Tables IV–V cost analysis (`tab:comp-cost`, `tab:comm-cost`) | — | — (analytical, from the papers; sources in each row's `%` comment) | — | — |
| Each baseline's own published figures (sanity check, not in the manuscript) | — | `scripts/paper_reproduction.py <scheme>` | `configs/methods/<scheme>.yaml` (`reproduction`) | `results/reproduction/<S id>/` |

Every results folder holds `rows.csv` (per request / sample), `metrics.json` (summary), `config_resolved.yaml`,
`run_info.json` (git commit, dirty flag, hardware, library versions, runtime) and `run.log`. Which run of
each experiment is current is recorded in `TASK.md` §1.1.
