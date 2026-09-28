# Scheme × Experiment Capability Matrix

Which scheme can serve as a baseline for which experiment of the VeRedact-PQ evaluation, and what
published numbers exist. Scheme ids and workflows: `config/schemes.toml`. Experiments: manuscript
Sec. Evaluation (`overleaf/VeRedact.md`).

Legend: **✓** mechanism present and the paper reports comparable numbers · **△** partial (some
configurations only, or must be re-implemented) · **✗** mechanism absent · **B** listed as a baseline
for that experiment in the manuscript.

## 1. Summary

| Id | Scheme | Exp 1 Latency/TP | Exp 2 Auth | Exp 3 Audit | Exp 4 Verify | Exp 5 Gas |
|:--|:--|:-:|:-:|:-:|:-:|:-:|
| S1 | Li et al. [1] (Improved DCH) | △ | △ **B** | ✗ | △ | ✗ |
| S2 | EAQ-VRBC [13] | △ | ✗ | ✓ **B** | ✓ **B** | ✓ |
| S3 | Liu et al. [27] (ETCH) | △ **B** | △ **B** | ✗ | △ | ✗ **B** |
| S4 | J. Xue et al. [34] (REBS) | △ | △ | ✗ | △ | ✗ |
| B-ref14 | Huang et al. [14] | **B** | | | | **B** |
| B-ref15 | Dong et al. [15] | | **B** | | | |
| B-ref17 | Wang et al. [17] | **B** | | | | **B** |
| B-ref20 | Miao et al. [20] | | | **B** | **B** | |
| B-ref33 | Xue et al. [33] | **B** | | **B** | **B** | **B** |

- S4 (REBS) is no longer a baseline in the manuscript; it stays for Table I / related work.
- B-ref* rows have no PDF in `Scheme/`, so their capability cells are not assessed; the benchmark
  models them from the manuscript's Table IV row (TODO-VERIFY).

## 2. Published numbers usable per experiment (S1–S3)

| Exp | Scheme | What the paper reports |
|:--|:--|:--|
| 1 | S3 ETCH | End-to-end redaction < 0.38 s at 33 redactors, RTT 300 ms; Adapt vs t = 3…33. No throughput vs λ. |
| 1 | S2 EAQ-VRBC | Redact compute vs #tx/block 50–500 (~2–4.5 ms); trusted single redactor. |
| 2 | S1 Li [1] | Collision per party, t = 5…45: flat (0.23–14 ms by pairing type); KeyGen quadratic. |
| 2 | S3 ETCH | Adapt vs t (TCH/DCH/VDCH/ETCH); Hash −50%, Adapt −22.26%, Verify −51.78%. |
| 3 | S2 EAQ-VRBC | Audit proof gen 0.040–0.478 s vs VRBC 3.16–8.78 s (c = 50…500); query gen ~1.2–2 ms (index 100–51,100). |
| 4 | S2 EAQ-VRBC | Audit verify 2.7–32.5 ms vs VRBC 3.65–4.14 s; query verify ~7.5 ms; aggregated non-membership batch verification. |
| 4 | S1/S3/S4 | Single-redaction Verify: Improved DCH 2.14–13.72 ms; ETCH ~3 ms; REBS ChVer ~3 ms (constant). |
| 5 | S2 EAQ-VRBC | Ropsten gas (Gwei): setup 71,768 · upload 254,526 · redact 104,788 · query 132,913 · audit 158,336. Re-measure on Besu. |

No scheme reports throughput against arrival rate λ; Exp 1 baselines must be re-implemented (done in `benchmark/`).

## 3. Open manuscript issues

| # | Issue | Where |
|:--|:--|:--|
| 1 | Stray `\section{Evaluation} skeleton in VedRedact.tex)` prints a junk duplicate heading | `VeRedact.tex` line ~2592 |
| 2 | ref1 and ref30 are the same paper (Li et al. 2025) | bibliography |
| 3 | Table I row says "Jia *et al.* [1]" but ref1 is Li *et al.* | Table I |
| 4 | "VRBC [13]" is used as the name, but ref13 is EAQ-VRBC (Zhang *et al.*) | Table I, Sec. Evaluation |
| 5 | PDFs missing for baselines [14], [15], [17], [20], [33] | `Scheme/` |
| 6 | Gas estimate: each checkpoint carries a 3,309-B ML-DSA signature, so VeRedact-PQ costs more per redaction than hash-only baselines below ~64 redactions/batch | Exp 5 |
