# Paper artifact manifest

Every number in the manuscript (`Overleaf/VeRedact-2.tex`) maps to one config, one script run and one results
folder. `<tier>` is `experiment` for the paper; `smoke` and `pilot` exist only to test the pipeline.
Regenerate everything with `make all TIER=experiment` (on the server) or, from fetched results,
`make tables figures TIER=experiment`.

| Paper item | Generated file | Script | Config | Results path |
|:--|:--|:--|:--|:--|
| Table: Execution Time of Cryptographic Primitives (`tab:primitives`) | `Overleaf/tables/tab_primitives.tex` | `Benchmark/scripts/make_tables.py` | `Benchmark/configs/experiments/exp00_primitives.yaml` | `Benchmark/results/exp00_primitives/<method>/<tier>/` |
| Fig. 3 Redaction performance (`fig:exp1_redaction`) | `Result/Pdf/exp1_redaction_throughput.pdf` | `Benchmark/scripts/make_figures.py` | `Benchmark/configs/experiments/exp01_redaction_throughput.yaml` | `Benchmark/results/exp01_redaction_throughput/<method>/<tier>/` |
| Fig. 4 Authorization latency (`fig:exp2_auth`) | `Result/Pdf/exp2_authorization_latency.pdf` | `Benchmark/scripts/make_figures.py` | `Benchmark/configs/experiments/exp02_authorization_latency.yaml` | `Benchmark/results/exp02_authorization_latency/<method>/<tier>/` |
| Fig. 5 Audit efficiency (`fig:exp3_audit`) | `Result/Pdf/exp3_audit_efficiency.pdf` | `Benchmark/scripts/make_figures.py` | `Benchmark/configs/experiments/exp03_audit_efficiency.yaml` | `Benchmark/results/exp03_audit_efficiency/<method>/<tier>/` |
| Fig. 6 Verification time (`fig:exp4_verify`) | `Result/Pdf/exp4_verification_time.pdf` | `Benchmark/scripts/make_figures.py` | `Benchmark/configs/experiments/exp04_verification_time.yaml` | `Benchmark/results/exp04_verification_time/<method>/<tier>/` |
| Fig. 7 Gas consumption (`fig:exp5_gas`) | `Result/Pdf/exp5_gas_consumption.pdf` | `Benchmark/scripts/make_figures.py` | `Benchmark/configs/experiments/exp05_gas_consumption.yaml` | `Benchmark/results/exp05_gas_consumption/<method>/<tier>/` |
| Table: Gas per contract operation (`tab:gas`) | `Overleaf/tables/tab_gas.tex` | `Benchmark/scripts/make_tables.py` | `Benchmark/configs/experiments/exp05_gas_consumption.yaml` | `Benchmark/results/exp05_gas_consumption/veredact/<tier>/` |
| Table: Default Experimental Parameters (`tab:params`) | — (values) | — | `Benchmark/configs/base.yaml`, `Benchmark/configs/datasets/synthetic_ledger.yaml`, `Benchmark/configs/methods/veredact.yaml` | — |
| Table I capability marks for the four baselines (`tab:comparison`) | — | `Benchmark/scripts/capabilities.py` | `Benchmark/configs/methods/*.yaml` | — (from each implementation's `capabilities()`) |
| Tables IV–V cost analysis (`tab:comp-cost`, `tab:comm-cost`) | — | — (analytical, from the papers; sources in each row's `%` comment) | — | — |
| Each baseline's own published figures (sanity check, not in the manuscript) | — | `Benchmark/scripts/paper_reproduction.py <scheme>` | `Benchmark/configs/methods/<scheme>.yaml` (`reproduction`) | `Benchmark/results/reproduction/<S id>/` |

Every results folder holds `rows.csv` (per request / sample), `metrics.json` (summary), `config_resolved.yaml`,
`run_info.json` (git commit, dirty flag, hardware, library versions, runtime) and `run.log`. Which run of
each experiment is current is recorded in `TASK.md` §1.1.
