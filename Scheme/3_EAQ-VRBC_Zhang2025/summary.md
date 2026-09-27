# Efficient Auditing and Querying in Verifiable Redactable Blockchain: A Lightweight VDS Protocol with Integrity Verification

| Field | Value |
|:---|:---|
| **Authors** | Xiaoxu Zhang, Zhipeng Cai, Keyan Chen, Guanxiong Ha, Chunfu Jia (Nankai University) |
| **Venue** | IEEE TrustCom 2025 (24th Int. Conf. on Trust, Security and Privacy in Computing and Communications), pp. 504–511 |
| **DOI** | 10.1109/Trustcom66490.2025.00062 |
| **Source PDF** | `Efficient_Auditing_and_Querying_in_Verifiable_Redactable_Blockchain_A_Lightweight_VDS_Protocol_with_Integrity_Verificat.pdf` |
| **Short name** | **EAQ-VRBC** (Zhang *et al.*) — auditable VDS protocol for redactable blockchains |
| **Paper type** | Auditing/query protocol + Python prototype + Ethereum gas measurement |
| **Keywords** | Verifiable redactable blockchain, data auditing, RSA accumulator, chameleon hash, verifiable data streaming |

> Note on citation: VeRedact-PQ compares with "VRBC [13]". **VRBC = VRBCIA** here (Tian *et al.*, IEEE TC 2022), which this paper re-implements as its baseline. So this PDF gives numbers for **both EAQ-VRBC and VRBC/VRBCIA** (plus AMVA17 = Ateniese *et al.*).

---

## 1. Abstract (summary)

- Redaction lets one block have **multiple valid versions** → malicious full nodes can feed **old versions** to light nodes.
- **EAQ-VRBC**: auditable **Verifiable Data Streaming (VDS)** protocol with a **dynamic RSA-accumulator revocation list** of outdated blocks.
- Freshness proven by **non-membership proofs** (only the latest version is valid).
- Integrity via **identity-based RSA signature auditing** (no PKI).
- Query/audit verification ≈ **one order of magnitude** cheaper than prior auditable VDS for RBC.

## 2. Problem Statement

- **Old-version deception:** light nodes (LN) hold only headers and trust full nodes (FN); after redaction an FN can serve a stale block.
- **CAT/BAT-based VDS** (e.g., VRBCIA) costs $O(\log n)$ per query and needs commitment updates along the path on each redaction.
- **PKI-based auditing** does not fit multi-miner ledgers.

## 3. Contributions

1. **Dynamic RSA-accumulator revocation** of old block versions; non-membership proof = freshness proof.
2. Non-membership proofs **without hash-to-prime**, **aggregatable** (batch verification), $O(1)$ generation/verification.
3. **Identity-based RSA tag auditing** with low query/audit verification cost.

## 4. Related Work

| Area | Works | Limitation noted |
|:---|:---|:---|
| Redactable blockchain | Ateniese RBC (AMVA17) | Multiple valid versions, no freshness |
| VDS | Schröder CAT [7], Krupp [8], VeriStream [9] | log(n) cost, single-item queries, costly updates |
| Light-node verification | [10]–[12] | Trust FN |
| Blockchain auditing | BLIND [13], Tian [14], Zhang [15] | PKI-based, single-user |
| Auditable VRBC | **VRBCIA [21]** (BAT-based) | Path commitment aggregation, log(n) verify |

## 5. Preliminaries

- **Redactable block:** $B_i=(h_{i-1},ch_i,m_i,Y_i,r_i,ctr_i)$; $ch_i=CH(h_{i-1},m_i,Y_i,r_i)$ over MHT root $m_i$; $h_i=H(ch_i,ctr_i)$.
- **Strong RSA assumption:** given $N=pq$ (safe primes), $u\in\mathbb{Z}_N^*$, hard to find $(v,e>1)$ with $v^e\equiv u$.
- **Shamir's trick:** $v^x\equiv u^y$, $\gcd(x,y)=1$ ⇒ compute $w$ with $w^x\equiv u$.

## 6. System Model

| Entity | Role | Trust |
|:---|:---|:---|
| **System Manager (SM)** | Public params, block tags, performs redactions | Fully trusted (e.g., committee) |
| **Miner** | Maintains ledger, updates revocation list, uploads blocks, starts audits | — |
| **Third-Party Auditor (TPA)** | Light node; verifies query/audit responses | — |
| **Auditee (FN)** | Full ledger; verifies redactions, generates proofs | Potentially malicious |

## 7. Security Model

- **Soundness:** Auditee cannot pass an audit without storing all challenged blocks.
- **Controlled redaction:** from a collision, no one can extract the trapdoor; only trapdoor holders redact.
- **Forward dynamic accumulator security:** under strong RSA, FN can't prove a revoked (old) block is current.

## 8. Scheme Construction

- **Setup:** SM builds $N=pq$ ($p=2p'+1$, $q=2q'+1$), $QR_N$ generator $g$; hashes $H_0$–$H_3$, $H_1\to$ odd numbers (no hash-to-prime); $\Upsilon_1,\Upsilon_2$ for challenge indices/coefficients.
  - Master keys $pk=(e,N)$, $sk=d$, $ed\equiv1$.
  - Miner identity keys: $sk_i=H_3(ID_i)^d$, $pk_i=H_3(ID_i)$.
  - Accumulator $acc(\emptyset)=u$; revocation list $R$; update log $upmsg_i=(v,acc,acc')$.
  - Chameleon trapdoor $TK=(x,y)$, hash key $HK=(X,Y)=(g^x,g^y)$.
- **Upload:** $ch_i=(X\cdot Y)^{H_2(h_{i-1}\|m_i,Y)}g^{r_i}$; SM makes tag $t_{s'}=(S_{s'},v)$ with $S_{s'}=v^d\prod sk_i^{c_{s'}}$, $c_{s'}=H_0(s'\|h_{s'}\|v)$; TPA checks tag and CH.
- **Redaction (double-trapdoor CH):**
  - Long-term key $k_s=H_2(h_{s-1}\|m_s,Y_s)(x+y)+r_s$.
  - Ephemeral $y_{s'}=H_3(x,m_{s'})$, $Y_{s'}=g^{y_{s'}}$.
  - $r_{s'}=k_s-H_2(h_{s-1}\|m_{s'},Y_{s'})(x+y_{s'})$; $ch_s$ unchanged.
- **Query:** TPA sends index $s$; Auditee returns $m_s$ + $\pi_q=\{t_{s'},hh_{s'},\bar w_x\}$ where $\bar w_x=(a,B,s)$ is a non-membership witness (Alg. 1).
  - TPA checks $u^{a\theta'}B^{H_1(x)/\prod s[i]}=u$, the tag, and the CH value.
- **Audit:** Challenge $(i',r_1,r_2)$ → indices $\alpha_i$, coefficients $\beta_i$; Auditee returns $P=\{AGGE,\mu,\bar w_{x_1..x_{i'}}\}$ with aggregated tags and **aggregated non-membership witness** (Alg. 2, NI-SimPoE proofs); TPA verifies with Alg. 3 ($CD\equiv u$).
- **Update:** Miner adds old tag hash $H_1(s'\|hh_{s'})$ to accumulator, issues new tag; Auditee swaps block data; SM updates public params.

### Algorithms

| Alg. | Name | Purpose |
|:---|:---|:---|
| 1 | NonMemWitCreate | Non-membership witness $(a,B,s)$ for one tag |
| 2 | Non-membership Witness Aggregation | Recursively merge witnesses; NI-SimPoE for $C=u^{a'}$, $D=B'^{x_1x_2'}$ |
| 3 | Verify Aggregated Witness | Check factors ≤ $2^\tau$, PoE proofs, $CD\equiv u \pmod N$ |

## 9. Security Analysis

- **Theorem 1 (Correctness):** query and audit equations hold (non-membership + tag).
- **Theorem 2 (Soundness):** forging $P'\ne P$ breaks RSA; advantage ≤ $2^{-\lambda}$.
- **Controlled redaction:** double-trapdoor CH.
- **Accumulator security:** collision-resistant $H_1$ + adaptive root assumption (ROM), strong RSA.
- **Not covered:** post-quantum security, threshold/decentralized redaction (SM is a single trusted redactor), policy/ZK compliance.

## 10. Performance Evaluation

### 10.1 Setup

| Item | Value |
|:---|:---|
| Baselines | AMVA17 (Ateniese RBC), VRBCIA / VRBC (Tian *et al.*) |
| Implementation | Python, Petlib, py_ecc |
| On-chain | Ethereum **Ropsten** testnet (gas in Gwei) |
| Machine | Intel i9-12900H 2.5 GHz, 16 GB RAM, Ubuntu 22.04.5 |
| Security | 2048-bit RSA modulus (112-bit) |
| Block data | 16 B per block |
| Repetitions | 30 runs, averaged |
| VRBCIA BAT | q = 2, level = 4, 15 nodes |

### 10.2 Communication / Storage — Table II

| System | Setup | Upload | Redaction | Block Query | Audit |
|:---|:---|:---|:---|:---|:---|
| AMVA17 | $\lvert BH\rvert+m\lvert Tx\rvert+2(\lvert\mathbb{Z}_p\rvert+\lvert\mathbb{G}\rvert)$ | $\lvert BH\rvert+m\lvert Tx\rvert+\lvert\mathbb{G}\rvert+2\lvert\mathbb{Z}_p\rvert$ | $\lvert BH\rvert+m\lvert Tx\rvert+3\lvert\mathbb{Z}_p\rvert$ | – | – |
| VRBCIA | $\lvert BH\rvert+m\lvert Tx\rvert+4(N+1)\lvert\mathbb{G}\rvert$ | $\ldots+(q+1)\lvert\mathbb{G}\rvert+2\lvert\mathbb{Z}_p\rvert$ | $\ldots+2\lvert\mathbb{G}\rvert+2\lvert\mathbb{Z}_p\rvert$ | $\ldots+(L+4)\lvert\mathbb{G}\rvert+4\lvert\mathbb{Z}_p\rvert+\lvert idx\rvert$ | $\rho c(\lvert BH\rvert+m\lvert Tx\rvert)+(3\rho+1)(\lvert\mathbb{G}\rvert+\lvert\mathbb{Z}_p\rvert)$ |
| EAQ-VRBC | $\ldots+n\lvert\mathbb{Z}_N\rvert+2\lvert QR_N\rvert$ | $\ldots+2\lvert\mathbb{Z}_N\rvert+2\lvert QR_N\rvert$ | $\ldots+3\lvert\mathbb{Z}_N\rvert$ | $\ldots+2\lvert\mathbb{Z}_N\rvert+2\lvert QR_N\rvert+\lvert idx\rvert$ | $c(\lvert BH\rvert+m\lvert Tx\rvert)+(c+4)\lvert\mathbb{Z}_N\rvert+6\lvert QR_N\rvert$ |

*"…" = $\lvert BH\rvert+m\lvert Tx\rvert$.*

### 10.3 Computation — Table III

| System | Setup | Upload | Redaction | Block Query | Audit |
|:---|:---|:---|:---|:---|:---|
| AMVA17 | $1M+1H+3Exp$ | $1M+(2^{l+1}+2)H+4Exp$ | $(2^{l+1}+2)H+3Exp$ | – | – |
| VRBCIA | $1M+2qH+3N\,Exp$ | $1M+(2^{l+1}+3q+2)H+(N+q+1)Exp+2Mul$ | $(2^{l+1}+2L+4)H+2(L+1)Exp+3Mul$ | $(qL+2^{l+1})H+(2N+1+L)Exp+(L+2)Pair+2(c-1)Mul$ | $c\rho(q+1+2^{l+1})H+(2N+c\rho)Exp+(c\rho+1)Pair+2(c-1)(\rho-1)Mul$ |
| **EAQ-VRBC** | $1M+(n+2)Exp+(6+n_i)H$ | $1M+(2^{l+1}+4)H+2(n_i+3)Exp+2(n_i-1)Mul$ | $(2^{l+1}+5)H+4Mul+2Exp$ | $7Exp+(2^{l+1}+4+rl)H+Inv+6Mul$ | $(8c-8)Exp+2(c-1)Inv+(5c-4)Mul+c\cdot2^{l+1}H$ |

### 10.4 On-Chain Gas — Fig. 3 (Gwei)

| Phase | AMVA17 | VRBCIA | EAQ-VRBC |
|:---|---:|---:|---:|
| Setup | 53,768 | 81,311 | 71,768 |
| Upload (per block) | 71,769 | 81,025 | 254,526 (90.3% tag storage/verify) |
| Redact | 53,768 | 81,037 | 104,788 |
| Query | – | 145,671 | 132,913 |
| Audit | – | 157,225 | 158,336 (constant) |

### 10.5 Off-Chain — Audit (Figs. 4–5, seconds, vs. #challenged blocks c)

| c | Proof gen VRBCIA | Proof gen EAQ-VRBC | Verify VRBCIA | Verify EAQ-VRBC |
|---:|---:|---:|---:|---:|
| 50 | 3.159 | 0.03967 | 4.098 | 0.00266 |
| 100 | 3.787 | 0.11736 | 4.139 | 0.00544 |
| 150 | 4.414 | 0.15711 | 3.987 | 0.01041 |
| 200 | 5.041 | 0.21182 | 3.653 | 0.01372 |
| 250 | 5.669 | 0.10984 | 4.054 | 0.01121 |
| 300 | 6.296 | 0.34513 | 3.956 | 0.01843 |
| 350 | 6.916 | 0.33863 | 4.073 | 0.02115 |
| 400 | 7.537 | 0.22420 | 3.660 | 0.02635 |
| 450 | 8.157 | 0.35515 | 3.682 | 0.02842 |
| 500 | 8.777 | 0.47818 | 3.704 | 0.03251 |

### 10.6 Off-Chain — Query (Figs. 6–7, seconds, vs. queried block index)

| Index | Proof gen VRBCIA | Proof gen EAQ-VRBC | Verify VRBCIA | Verify EAQ-VRBC |
|---:|---:|---:|---:|---:|
| 100 | 0.028 | 0.00127 | 3.590 | 0.00758 |
| 300 | 0.034 | 0.00199 | 3.582 | 0.00758 |
| 700 | 0.044 | 0.00187 | 3.741 | 0.00754 |
| 1500 | 0.065 | 0.00178 | 3.218 | 0.00755 |
| 3100 | 0.073 | 0.00153 | 3.291 | 0.00754 |
| 6300 | 0.106 | 0.00185 | 2.999 | 0.00757 |
| 12700 | 0.136 | 0.00185 | 3.130 | 0.00752 |
| 25500 | 0.146 | 0.00188 | 3.123 | 0.00754 |
| 51100 | 0.158 | 0.00123 | 2.899 | 0.00755 |

### 10.7 Off-Chain — Upload & Redact (Figs. 8–9, vs. #tx per block 50–500)

| Operation | AMVA17 | VRBCIA | EAQ-VRBC |
|:---|:---|:---|:---|
| Upload | ~8–10 ms | ~9–15 ms | ~8–10 ms (≈ AMVA17) |
| Redact | ~2–4.5 ms | ~12–16 ms | ~2–4.5 ms (≈ AMVA17) |

### 10.8 Headline Gains vs. VRBCIA

| Metric | Reduction |
|:---|---:|
| Query proof generation | 99% |
| Query proof verification | 99.7% |
| Audit proof generation | 94.3% |
| Audit proof verification | 98.6% |

## 11. Limitations (relative to VeRedact-PQ)

- **Centralized, fully trusted SM** performs redactions → no threshold/committee authorization.
- **Not post-quantum** (RSA, DL-based CH).
- **No throughput / arrival-rate / end-to-end redaction latency**; no batching.
- **No policy or ZK verification** of requests; no requester authentication pipeline.
- Audit covers storage integrity + version freshness only; no "who authorized / which policy" query types.
- Gas measured on deprecated **Ropsten**; upload gas higher than baselines.

## 12. Conclusion

- Dynamic RSA-accumulator revocation + identity-based RSA tags stop old-version deception.
- Query/audit verification ~10× (up to 99.7%) cheaper than VRBCIA; lower off-chain cost overall.
