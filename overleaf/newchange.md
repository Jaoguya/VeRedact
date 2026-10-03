# Manuscript changes needed — VeRedact-2.tex

The manuscript is final; it is never edited here. Each item: line in `VeRedact-2.tex`, the exact text to
find, and the replacement to paste. Work from the bottom up so line numbers stay valid.
Opened 2026-10-03, after aligning the code with the final manuscript for the full experiment.

## A. Now — the code does more than the cost tables say

### A1. Line 2681 — Table IV, VeRedact-PQ, Request Validation: the VPS also signs the admission receipt $rc_i$ (Phase 3 Step 5)
Find: `$2T_V+T_{ZV}+T_S+T_{\mathrm{PRF}}$`
```latex
$2T_V+T_{ZV}+2T_S+T_{\mathrm{PRF}}$
```

### A2. Line 2683 — Table IV, VeRedact-PQ, Redaction Execution: Phase 5 Step 1 verifies the $t$ approvals in $Auth_e^B$ once per ABRRR batch
Find: `$|\Omega_e|(t\,T_{PA}+T_{CB}+T_{CH}+T_S)$`
```latex
$t\,T_V+|\Omega_e|(t\,T_{PA}+T_{CB}+T_{CH}+T_S)$
```

### A3. Line 2784 — Table V, VeRedact-PQ, Request Submission: the requester receives the signed receipt $rc_i$
Find: `& $|R|+|\sigma|+|\pi|$`
```latex
& $|R|+2|\sigma|+|\pi|$
```

### A4. Line 1275 — Phase 4 Step 1: $f$ is never defined. The code uses the expected arrivals within $T_{\max}$; $|\mathcal{Q}_e|$ acts as the close condition (a batch closes once $|\mathcal{Q}_e|\ge B_e^{*}$)
Find: `=f(\lambda_e,|\mathcal{Q}_e|,T_{\max})`
```latex
=\lambda_e\,T_{\max}
```

### A5. Lines 2836-2838 — Experimental Setup: only the Besu validators run in Docker; committee members, the VPS and auditors run as processes on the same host
Find: `Consortium nodes,` … `were emulated using Docker` … `containers,`
```latex
The Besu validator nodes ran as Docker
containers, while committee members, the VPS, and auditors ran as
processes on the same host,
```

### A6. Lines 147 and 340 — `ref30` is the same paper as `ref1` (both: Li, Shen, Wu, IEEE TC 2025); each citation lists both
Find (line 147): `~\cite{ref1,ref2,ref6,ref30}.`
```latex
~\cite{ref1,ref2,ref6}.
```
Find (line 340): `~\cite{ref1,ref3,ref6,ref19,ref30}.`
```latex
~\cite{ref1,ref3,ref6,ref19}.
```
Then delete `\bibitem{ref30}` (line 3371) and its entry. Only the bibliography numbering after [29] is
affected if the references are renumbered; the baseline numbers [1], [13], [27], [34] do not change.

## B. Now — `[TBD]` values the code already fixes

### B1. Line 2834 — size and language of the implementation (count after the restructure, 2026-10-03: ~6,900 Python + 1,019 Rust + 119 Solidity lines)
Find: `\textbf{[TBD]} lines of \textbf{[TBD: language]} code`
```latex
approximately 8,000 lines of Python, Rust, and Solidity code
```

### B2. Line 2846 — STARK library
Find: `STARK proof system \textbf{[TBD: library]},`
```latex
STARK proof system (winterfell~0.13, Rescue-Prime credential registry, 42 queries, blowup 8, 16-bit grinding),
```

### B3. Line 2850 — PQCH construction
Find: `\textbf{[TBD: confirm construction]}.`
```latex
using a gadget-based lattice trapdoor with dealerless $t$-of-$n$ Shamir sharing of the trapdoor.
```

### B4. Line 2836 — operating system (fixed by `configs/aws.toml`)
Find: `running Ubuntu \textbf{[TBD]}.`
```latex
running Ubuntu 24.04.
```

### B5. Optional — tab:primitives (after line 2904): Table IV uses $T_E^{c}$ for Scheme [13]'s audit, but the primitive table has no row for it (the run measures it)
```latex
$T_E^{c}$ & RSA-3072 exponentiation~\cite{ref13} & [TBD] \\
```

## D. From the evaluation-code restructure (2026-10-03)

### D1. Lines 2867–2868 — one run per configuration point (author decision 2026-10-03), not 30 runs
Find: `used, and all reported results represent the mean of 30 independent runs` … `with 95\% confidence intervals.`
```latex
used. Each configuration point is executed once; reported values are medians (and 95th percentiles for
latency) over all requests or samples of that run, with 95\% confidence intervals of the mean.
```

### D2. Line 2928 — Table "Default Experimental Parameters"
Find: `Repetitions & 30 runs, 95\% confidence interval \\`
```latex
Runs & 1 per point; 30 samples per point (Exp.~2--4) \\
```

### D3. Optional — vector figures. The code writes each figure as both `.png` (current names) and `.pdf`
(`paper/figures/`). To use the vector version, change the extension in lines 2962, 3022, 3067, 3112, 3159:
Find: `{exp1_redaction_throughput.png}` (and the four others)
```latex
{exp1_redaction_throughput.pdf}
```

## C. After the full run — fill from `paper/` and `results/` (never from the papers)

| Line(s) | What | Source |
|:--|:--|:--|
| 2835-2836 | CPU, cores, clock; RAM | `results/<exp>/<method>/experiment/run_info.json` → environment (c7i.4xlarge: 16 vCPU, 32 GiB) |
| 2838 | netem delay | `configs/base.yaml` `ledger.netem_delay_ms` (now 10, marked CONFIRM) |
| 2852 | number of Besu validators | `configs/base.yaml` `ledger.validators` (now 7, marked CONFIRM) |
| 2889-2904 | primitive timings | `paper/tables/tab_primitives.tex` (median ± 95% CI) — paste the rows |
| 3195-3200 | gas per contract operation | `paper/tables/tab_gas.tex` |
| Exp. 1-4 result paragraphs | rewrite against the measured figures | `paper/figures/exp1..exp4_*.pdf` and `paper/tables/tab_significance.tex` (the manuscript's own NOTE at Exp. 1) |
