# Manuscript changes — Evaluation section, experiments only

Scope (author rule 2026-10-09): only Section V-C "Performance Analysis" of `overleaf/VeRedact-2.tex` changes.
Everything else (Sections I–IV, every formula, Tables III–V, the cost analyses) is final and is not touched.
No formula is changed here either: every math expression below is copied unchanged from the manuscript.

Style: the experiment text follows the journal ZK-Redact paper (`Scheme/zkredact/ZK-Redact-2.tex`, Sec.
"Performance Evaluation"): one compact Experimental Setup (implementation, primitives, ledger, host, dataset,
workload, measurement), then for each experiment one paragraph "This experiment evaluates X as Y varies from a
to b, comparing VeRedact-PQ with ..." followed by the results.

The experiments themselves are what the manuscript already describes (all internal variants, both audit
levels, both Exp. 5 skews); the code runs exactly that. Result paragraphs stay as they are until the full run,
then they are rewritten from the measured figures (section "After the full run").

Each item: the line range to replace and the full replacement, ready to paste. Work from the bottom up so the
line numbers stay valid.

---

## 1. Lines 3141–3155 — Experiment 5 description
Replace from `\subsubsection*{\textbf{Experiment 5: Blockchain Gas Consumption}}` through
`results are shown in Fig.~\ref{fig:exp5_gas}.` with:
```latex
\subsubsection*{\textbf{Experiment 5: Blockchain Gas Consumption}}

This experiment evaluates the on-chain cost of redaction as the number of
redactions per ABRRR batch increases as $m\in\{1,8,32,64,128,256\}$ under
Zipf skews $s\in\{0,0.8\}$, comparing VeRedact-PQ with
Refs.~\cite{ref1}, \cite{ref13}, \cite{ref27}, and~\cite{ref34}. Gas is
read from the transaction receipts of the Besu network; although the gas
price is zero in the permissioned deployment, gas usage is a deterministic
measure of on-chain computation and storage. The measured VeRedact-PQ
operations are policy and committee registration (Phase~1), batch-checkpoint
anchoring $A_b$ (Phase~2), authorization anchoring $H(Auth_e^B)$ (Phase~4),
redaction finalization, which atomically commits the updated checkpoints
$\{A_b'\}$ and SA-RLI state (Phase~5), and RAI checkpoint anchoring
$CP_e^A$ (Phase~6); each baseline is a contract storing the on-chain
redaction state its paper prescribes, one transaction per redaction. Each
configuration redacts 1{,}024 requests. Total gas per authorization round
and amortized gas per redaction are shown in Fig.~\ref{fig:exp5_gas}.
```

## 2. Lines 3093–3108 — Experiment 4 description
Replace from `\subsubsection*{\textbf{Experiment 4: Verification Time}}` through
`The results are shown in Fig.~\ref{fig:exp4_verify}.` with:
```latex
\subsubsection*{\textbf{Experiment 4: Verification Time}}

This experiment evaluates auditor-side verification of returned redaction
evidence as the number of verified records increases as
$n_Q\in\{10,10^2,10^3,10^4\}$, comparing VeRedact-PQ with
Refs.~\cite{ref13} and~\cite{ref1} in their original classical
instantiations. VeRedact-PQ is verified under two levels:
\textbf{Normal Audit}, which verifies validation attestations and the
committed $H(\pi_i^{PQ})$, and \textbf{Deep Audit}, which additionally
reconstructs $x_i$ and verifies $\pi_i^{PQ}$; the baselines' audits have a
single level. Verification time is decomposed into response signature and
query binding, RAI multiproof, committee approvals, validation attestations,
state-transition and PQCH checks, and PQZK verification. To evaluate
verification granularity, modified, substituted, and stale evidence is
injected into 1\%, 5\%, and 10\% of the returned records, and the fraction
of invalid records individually rejected and of valid records retained is
measured. Each configuration is verified 30 times. The results are shown in
Fig.~\ref{fig:exp4_verify}.
```

## 3. Lines 3050–3063 — Experiment 3 description
Replace from `\subsubsection*{\textbf{Experiment 3: Audit Efficiency}}` through
`Fig.~\ref{fig:exp3_audit}.` (the line that closes "The results are shown in") with:
```latex
\subsubsection*{\textbf{Experiment 3: Audit Efficiency}}

This experiment evaluates the service-side cost of Phase~6 auditing, namely
query resolution, evidence generation, and response size, as the number of
returned redaction records increases as $n_Q\in\{10,10^2,10^3,10^4\}$,
comparing VeRedact-PQ with Refs.~\cite{ref13} and~\cite{ref1}. The
redaction history is built beforehand and is not timed. To control evidence
sharing, the number of returned records per authorization batch is varied as
1, 4, 16, and 64. An internal variant, \textbf{Per-Record Evidence}, returns
an individual Merkle path and complete authorization evidence for every
record instead of a query-scoped multiproof with shared batch evidence. Each
configuration is queried 30 times. Response-generation time and response
size are shown in Fig.~\ref{fig:exp3_audit}.
```

## 4. Lines 3002–3018 — Experiment 2 description
Replace from `\subsubsection*{\textbf{Experiment 2: Transaction Authorization Latency}}` through
`The results are shown in Fig.~\ref{fig:exp2_auth}.` with:
```latex
\subsubsection*{\textbf{Experiment 2: Transaction Authorization Latency}}

This experiment evaluates the latency of Phase~4 multi-party authorization
as the committee size increases as $n\in\{4,7,10,16,32\}$ with
$t=\lfloor 2n/3\rfloor+1$ and the ABRRR batch size as
$m\in\{1,8,32,64,128,256\}$, comparing VeRedact-PQ with
Refs.~\cite{ref1} and~\cite{ref34}, which support distributed or
policy-based redaction authorization; Refs.~\cite{ref13} and~\cite{ref27}
define no separate authorization step. An internal variant, \textbf{Re-ZK},
in which committee members re-verify each PQZK proof instead of the VPS
attestation $\alpha_i$, is also evaluated. Authorization latency is measured
from batch closure to the availability of $Auth_e^B$, reported per batch and
amortized per request, and decomposed into attestation verification,
state-freshness checking, batch-commitment construction, and committee
signing and verification. Each configuration is measured over 30
authorization batches. The results are shown in Fig.~\ref{fig:exp2_auth}.
```

## 5. Lines 2934–2958 — Experiment 1 description
Replace from `\subsubsection*{\textbf{Experiment 1: Redaction Latency and Throughput}}` through
`recorded. The results are shown in Fig.~\ref{fig:exp1_redaction}.` with:
```latex
\subsubsection*{\textbf{Experiment 1: Redaction Latency and Throughput}}

This experiment evaluates end-to-end redaction performance as the request
arrival rate increases from 100 to 5{,}000 requests/s over the default
ledger, comparing VeRedact-PQ with Refs.~\cite{ref1}, \cite{ref13},
\cite{ref27}, and~\cite{ref34} and three internal variants:
\textbf{Per-Request}, in which each validated request is authorized and
executed individually without ABRRR or BIMC; \textbf{Fixed-Batch}, with a
static batch size of 64 and no workload-aware adaptation; and
\textbf{No-BIMC}, which retains ABRRR batching but performs an independent
Merkle update and PQCH adaptation for each authorized modification.
End-to-end latency is measured from request submission to blockchain
finalization of the updated checkpoint, covering Phases~3 to~5, and
throughput as the number of redactions finalized per second within a
60-s measurement window that follows a 10-s warm-up. To evaluate batch
locality, the Zipf skew is additionally varied as $s\in\{0,0.4,0.8,1.2\}$
at 100 requests/s, and the number of distributed PQCH adaptations per
1{,}000 finalized redactions is recorded. The results are shown in
Fig.~\ref{fig:exp1_redaction}.
```

## 6. Line 2928 — Table "Default Experimental Parameters", repetitions row
Find: `Repetitions & 30 runs, 95\% confidence interval \\`
```latex
Runs & 1 per configuration point (30 samples, Exp.~2--4) \\
```

## 7. Lines 2833–2875 — Experimental Setup (the body under `\subsubsection{Experimental Setup}`)
Replace from `The proposed VeRedact-PQ framework was implemented in approximately` through
`workflow, including per-request authorization and adaptation.` with:
```latex
VeRedact-PQ and the four baselines~\cite{ref1,ref13,ref27,ref34} are
implemented in approximately 9{,}100 lines of Python, Rust, and Solidity
code. PQSIG is instantiated with ML-DSA-65 (FIPS~204, NIST category~3)
through the Open Quantum Safe \texttt{liboqs} library; $H$, $H_1$, $H_2$,
and $H_A$ as domain-separated SHA3-256; and $\mathsf{PRF}$ as HMAC-SHA3-256
with 256-bit keys $K_{\mathrm{idx}}$ and $K_A$ ($\lambda=256$). PQZK is a
transparent hash-based STARK (winterfell~0.13; 42 queries, blowup factor~8,
16-bit grinding), consistent with the trapdoor-free setup of Phase~1, and
PQCH is an SIS-based chameleon hash following~\cite{ref10,ref17} with
dealerless $t$-of-$n$ sharing of its lattice trapdoor. Merkle structures,
BIMC, SA-RLI, and RAI use binary SHA3-256 trees with multiproof support.
The baselines are instantiated with their own classical primitives at about
128-bit security (RSA-3072, BLS12-381, secp256k1), since none of their
papers defines a post-quantum variant; each follows its original workflow,
and stages its paper does not define are reported as not supported.

The PBN is a 7-validator Hyperledger Besu network with QBFT consensus and a
2-s block period, run as Docker containers with a 10-ms inter-node delay set
by Linux \texttt{tc netem}; Solidity contracts anchor policy commitments,
committee configurations, batch checkpoints, and RAI checkpoints, while PQ
signatures are verified by the nodes before anchoring rather than inside the
contracts. The committee members, the VPS, the audit service, and the
auditor run as processes on one AWS c7i.4xlarge host (16 vCPU, 32\,GiB RAM,
Ubuntu 24.04); in Experiment~1, requesters sign and prove on two separate
c7i.48xlarge hosts so that the system under test keeps all of its cores.
Table~\ref{tab:primitives} reports the measured execution time of each
primitive.

The dataset contains $10^5$ synthetic enterprise transactions with
256\,B to 4\,KB payloads in transaction batches of $N$ leaves, 100
registered requesters, and 10 redaction policies. Redaction targets follow
a Zipf distribution with skew $s$, where $s=0$ corresponds to uniformly
distributed targets and larger $s$ concentrates requests on fewer
transaction batches, and request arrivals follow a Poisson process whose
rate is varied per experiment. Every scheme replays the same request trace
generated from one seed. Unless otherwise stated, the parameters in
Table~\ref{tab:params} are used; each configuration point is executed once,
and reported values are medians (95th percentiles for latency) over all
requests or samples of that run.
```

---

## Not changed (final)
- Sections I–IV, all formulas, Tables III–V and the cost-analysis subsections A and B of Section V.
- Figure environments and captions: the figures show what the captions say (variants, normal and deep audit,
  both skews), so no caption changes.

## After the full run — fill from `paper/` and `results/` (never from the papers)
| Where | What | Source |
|:--|:--|:--|
| Table "Execution Time of Cryptographic Primitives" | every `[TBD]` time | `paper/tables/tab_primitives.tex` |
| Table "Gas Consumption of VeRedact-PQ Contract Operations" | every `[TBD]` gas | `paper/tables/tab_gas.tex` |
| Results paragraphs of Experiments 1–5 | rewrite each to the measured figure, one paragraph per experiment in the ZK-Redact style | `paper/figures/exp1..exp5_*.pdf` (the manuscript's own NOTE at Experiment 1 asks for this) |
| Table "Default Experimental Parameters" | remove the square brackets once the values are confirmed | `configs/` |
