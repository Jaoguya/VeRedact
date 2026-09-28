# Attribute-Based Policy-Hiding Redactable Blockchain With Authorizable Verification for Energy Internet

| Field | Value |
|:---|:---|
| **Authors** | Jingting Xue, Liang Liu, Fagen Li, Ximin Jing, Wenzheng Zhang, Xiaojun Zhang, Yu Zhou (SWPU, UESTC, Inst. of Southwestern Communication) |
| **Venue** | IEEE Internet of Things Journal, vol. 12, no. 15, pp. 29570–29583, 1 Aug. 2025 |
| **DOI** | 10.1109/JIOT.2025.3569699 |
| **Source PDF** | `Attribute-Based_Policy-Hiding_Redactable_Blockchain_With_Authorizable_Verification_for_Energy_Internet.pdf` |
| **Short name** | **REBS** (Redactable Energy Blockchain Scheme), J. Xue *et al.* — VeRedact-PQ ref **[34]** |
| **Paper type** | Primitive/scheme design + crypto micro-benchmarks (no blockchain deployment) |
| **Keywords** | Attribute-based policy hiding, authorizable verification, distributed energy trading, privacy protection, redactable blockchain |

> Note on citation: VeRedact-PQ's experiment list names "Xue *et al.* [33]" (L. Xue, *Main–Auxiliary Architecture*, TDSC 2026). **This PDF is J. Xue *et al.* [34]**, a different paper.

---

## 1. Abstract (summary)

- P2P energy trading on blockchain can permanently store illegal/outdated data.
- **REBS**: transaction-level redaction with **partial attribute-based policy hiding** (attribute *values* hidden, names visible).
- **Multi-authority key generation** (MA-ABE) + **redactor attribute verification** by AVNs.
- **Time-updatable chameleon hash** → redaction only within a time window (prevents indefinite redaction).
- **Delegate** algorithm lets AVNs hand key-share distribution to other nodes (dynamic join/leave).

## 2. Problem Statement

- **Trapdoor security risk** — central holders or leaked keys.
- **Privacy leakage** — access policies expose redactors' attribute values.
- **Indefinite redaction** — a node that once held an attribute can redact forever, even after attribute change.
- **Static verifiers** — attribute-verification nodes can't join/leave.

## 3. Contributions

1. REBS for energy trading: attribute-based redaction policy, attribute↔trapdoor mapping, CHET for tx-level redaction.
2. **Partial policy hiding** via LSSS in a semi-open consortium chain.
3. **Time-limited redaction** (TimeUpdate) + **authorizable verification** (Delegate, re-encryption style); MA-ABE key distribution.
4. Proofs: indistinguishability, public/private collision resistance, partial policy hiding; performance evaluation.

## 4. Related Work — Table I

| Scheme | Technology | Dynamicity | Tx-level | Scalability | Decentralized perms | Attributes hidden |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| Ateniese 2017 [10] | CH | ✗ | ✗ | ✓ | ✗ | • |
| Deuber 2019 [12] | Voting | ✗ | ✗ | ✓ | ✓ | • |
| Derler 2019 [17] | CH, CP-ABE | ✗ | ✓ | ✓ | ✗ | ✗ |
| Jia 2021 [22] | CH | ✗ | ✓ | ✓ | ✗ | ✗ |
| Huang 2021 [27] | CH, Ring Sig | ✗ | ✗ | ✓ | ✓ | • |
| Xu 2021 [24] | CH, Sig | ✓ | ✓ | ✓ | ✗ | • |
| Jia 2022 [28] | CH, Accumulators | ✓ | ✗ | ✓ | ✓ | • |
| Ma 2022 [25] | CHET, CP-ABE | ✗ | ✓ | ✓ | ✓ | ✗ |
| Zhang 2023 [26] | CHET, CP-ABE | ✗ | ✓ | ✓ | ✓ | ✗ |
| Shen 2023 [29] | CHET, Accumulators | ✗ | ✗ | ✗ | ✓ | • |
| Li 2023 [16] | Voting | ✗ | ✗ | ✗ | ✓ | • |
| Shao 2023 [23] | CH | ✗ | ✓ | ✓ | ✓ | • |
| Xu 2023 [19] | CH, CP-ABE | ✗ | ✓ | ✓ | ✓ | ✗ |
| Li 2023 [30] | CH, MPC | ✓ | ✓ | ✓ | ✓ | • |
| Dai 2024 [31] | CH, Voting | ✗ | ✗ | ✗ | ✓ | • |
| Zhang 2024 [32] | CH, DPSS | ✗ | ✓ | ✓ | ✓ | • |
| Xu 2024 [33] | CH, ABE | ✗ | ✓ | ✗ | ✓ | ✗ |
| **REBS** | CHET, CP-ABE | ✓ | ✓ | ✓ | ✓ | ✓ |

*• = not applicable. Dynamicity = verifier nodes can join/leave. Scalability = compatible with classical chains.*

## 5. Preliminaries

- **Access structure / LSSS:** $A_{\ell\times m}\cdot\vec v$ gives shares; reconstruction constants $\mu_i$ with $\sum\mu_iA_i=(1,0,\dots,0)$.
- **(t,n) threshold → LSSS** via Vandermonde-like auxiliary matrix $M$ (Liu *et al.*), smaller than Lewko–Waters AND-OR conversion.
- **Predicate Encryption** (Katz *et al.*): attribute hiding.
- **MA-ABE** (Lewko–Waters): decentralized key distribution, IND-CCA2 (static).
- **CHET** (Camenisch *et al.*): chameleon hash with ephemeral trapdoor; strong indistinguishability, public & private collision resistance (RSA-like).

## 6. System Model

| Entity | Role | Trust |
|:---|:---|:---|
| **Transaction Sender (TS)** | Creates tx, defines redaction policy (attributes + time) | — |
| **Transaction Redactor (TR)** | Satisfies policy; redacts | — |
| **Attribute Verification Node (AVN)** | Consensus node; issues attribute key shares; validates redactions; can join/leave | Semi-honest (may collude) |
| **Attribute Management Center (AMC)** | Issues CH keys to TRs, oversees AVNs | Trusted (can be reputable AVNs) |
| **Redactable Consortium Blockchain (RCB)** | Energy-trading ledger | — |

## 7. Design Goals

- Fine-grained (tx-level) redaction within the TS-specified period.
- Dynamic AVN participation with forward/backward security.
- Consensus correctness on original and redacted hashes.
- Indistinguishability, collision resistance, privacy of attribute values.

## 8. Security Models

| Property | Experiment |
|:---|:---|
| Indistinguishability | $\text{IND}^{REBS}_A$: tell CHash vs. ChCld randomness |
| Public collision resistance | $\text{PubCollRes}$: outsider finds collision with ChCld oracle |
| Private collision resistance | $\text{PriCollRes}$: insider without satisfying attributes finds collision |
| Partial policy hiding | $\text{PartPolHid}$ game: distinguish $T_0$ vs. $T_1$ attribute values |

## 9. Scheme Construction

### 9.1 System Initialization

- **GPGen (AMC):** RSA $(n,p,q)$; composite-order pairing $(N=p_1p_2p_3,\mathbb{G},\mathbb{G}_T,e,g)$; $sk_{AMC}=(p,q,\alpha)$, $pk_{AMC}=(n,g^\alpha)$; large prime $\breve e>\breve n$; hashes $H, H_{ID}, H_{sig}$; encode/decode.
- **KeyTS Gen:** $sk_{TS}=\vartheta$, $pk_{TS}=g^\vartheta$.
- **KeyTR Gen (AMC):** $k_{TR}=(p,q)$, $Sig_{AMC}=H_{ID}(1,ID_{TR})^\alpha$.
- **KeyAVN Gen:** $sk_{AVN_i}=(\varepsilon_i,\eta_i)$, $pk_{AVN_i}=(e(g,g)^{\varepsilon_i},g^{\eta_i})$.

### 9.2 Transaction Generation

- **LSSSConvert:** policy tree → threshold string → LSSS matrix; policy $RP=(A_{\ell\times m},\rho,T)$, $T$ hidden.
- **CHash (TS):**
  1. Ephemeral RSA $(\tilde n,\tilde p,\tilde q)$; $Trap=encode(\tilde p,\tilde q)$, $h_{Trap}=H(Trap)$.
  2. $h=H(Tx)^{t}\,r^{\breve e}\bmod n\tilde n$ with timestamp $t$.
  3. Encrypt Trap under policy: $c_0=Trap\cdot e(g,g)^s$, $c_{1,l}=e(g,g)^{\lambda_l}e(g,g)^{\varepsilon_{\rho(l)}t_{\rho(l)}r_l}$, $c_{2,l}=g^{r_l}$, $c_{3,l}=g^{r_l\eta_{\rho(l)}}g^{\theta_l}$.
  4. Broadcast $(h,t,r,Info_{Trap})$ + Tx.
- **ChVer (AVNs):** before $t+\Delta t$, check $h=H(Tx)^t r^{\breve e}\bmod n\tilde n$.

### 9.3 Transaction Redaction

- **AttrKeyGen (AVN_i):** verify $e(g,Sig_{AMC})=e(g^\alpha,H_{ID}(1,ID_{TR}))$; issue $k_{attr_i}=g^{\varepsilon_i t_{TR_i}}h_{ID}^{\eta_i}$.
- **ChCld (TR):** recover $Trap'$ from $Info_{Trap}$ with LSSS constants, check $h_{Trap}$; compute $\breve d$ with $\breve e\breve d\equiv1 \bmod \phi(n\tilde n)$; $\tilde r=(h\cdot H(Tx')^{-t})^{\breve d}$; ChVer; broadcast.
- **TimeUpdate (TS):** $r'=r\cdot((H(Tx)^{\Delta t})^{-1})^{\breve d}$; sign $Sig_{TS}=H_{sig}(Tx,r',ID_{TS})^\vartheta$; new tuple $(h,t+\Delta t,r',Info_{Trap})$.

### 9.4 Authorization Phase

- **Delegate:** remove $AVN_i$, add $\widetilde{AVN}_i$ with fresh $(\tilde\varepsilon_i,\tilde\eta_i)$; re-randomize $Info_{Trap}$ components for affected TRs; re-issue attribute keys.

## 10. Security Analysis

| Theorem | Property | Assumption |
|:---|:---|:---|
| 1 | Indistinguishability | CHET strong IND (one-more RSA inversion) |
| 2 | Public collision resistance | CHET collision resistance (RSA) |
| 3 | Private collision resistance | CHET private CR + MA-ABE IND-CCA2 + DS EUF-CMA; $\Pr[G_0]\le q(\cdot)$ |
| 4 | Partial policy hiding | Lewko–Waters assumptions 1–3 + Caro assumption 4 (dual-system games) |

- **Not covered:** post-quantum security, threshold committee signing, batching, audit/query of redaction history, replay/freshness beyond time window.

## 11. Performance Evaluation

### 11.1 Theoretical Computation — Table II

| Scheme | KeyGen | Hash | Verify | Adapt |
|:---|:---|:---|:---|:---|
| PCH [17] | $(15+9s)E+(9+6s)M+(6+6s)H$ | $(7+6l+9s)E+(4+3l+6sl)M+(3+6l+6s)H+SE$ | $2E+2M+2BP$ | $(11+6k+6l+9sl)E+(10+6k+6l+6sl)M+6BP+(3+6l+6s)H+SE$ |
| DPCH [25] | $4sE+2sM+2BP+3sH$ | $(3+6l)E+(3+2l)M+(1+2l)BP+(2+2l+2s)H+SE$ | $2E+2M+2BP$ | $(3+k+6l)E+(3+4k+2l)M+(1+3k+2l)BP+(4+2l+2s)H+SE$ |
| PCHA [19] | $(15+9s)E+(9+6s)M+(6+6s)H$ | $(23+6l+9s)E+(4+3l+6sl)M+3BP+(5+12l+6s)H+SE$ | $4E+3M+3BP+2H$ | $(32+7k+6l+9s)E+(17+8k+3l+6sl)M+9BP+(11+k+13l+6s)H+2SE$ |
| PRHBS [33] | $(3+4s)E+(1+2s)M$ | $(7+7l)E+(3+2l)M+2BP+3H$ | $2E+M+BP$ | $(1+k)E+(1+3k)M+(1+3k)BP+H+SE$ |
| **REBS** | $2sE+sM+2BP+(1+s)H$ | $(2+5l)E+(2+2l)M+(1+2l)BP+2H$ | $E+M+BP$ | $(1+k)E+(1+2k)M+2kBP+2H$ |

- Extra REBS ops: **Delegate** $6kE+4kM+7kBP+2kH$; **Update** $3E+2M+2BP+H$.
- *E: exp; M: mult; BP: pairing; H: hash; SE: symmetric enc; l: #policy attributes; s: #user attributes; k: #attributes in decryption key (k ≤ l).*

### 11.2 Experimental Setup

| Item | Value |
|:---|:---|
| Implementation | Python + Charm-Crypto 0.5 (PBC, GMP, OpenSSL) |
| Machine | Intel i5-8250U 1.8 GHz, 8 GB RAM |
| Curves / sizes | SS512 pairing, RSA-1024, SHA-256 |
| Repetitions | 100, averaged |
| Attributes | l = 10 → 100 |
| Baselines | PCH [17], DPCH [25], PCHA [19], PRHBS [33] |
| Blockchain platform | **None** |

### 11.3 Computation Results (Figs. 3–6)

| Algorithm | Behavior | REBS value |
|:---|:---|:---|
| KeyGen (Fig. 3a) | Linear in l; REBS lowest | < 0.2 s at l = 100 |
| Hash (Fig. 3b) | Linear; REBS lowest (PCH/PCHA ~3 s at 100) | ~1 s at l = 100 |
| Verify (Fig. 3c) | **Constant** in l | ~0.003 s |
| Adapt (Fig. 3d) | PCH explodes (~28 s at 100); others small | lowest |
| Delegate (Fig. 3e) | Linear | 0.10 s (l=10) → **0.56 s** (l=100) |
| Update (Fig. 3f) | Constant | **0.0057 s** |
| Total (Fig. 4, l=100) | vs. PRHBS / DPCH | −0.130 s / −0.801 s |
| Real env. (Fig. 5, l=40, 20 runs) | min / mean / max | 0.320 / 0.432 / 0.608 s |
| Breakdown (Fig. 6, s=20,k=15) | Hash vs. Delegate share, l 20→30 | 36%→46% / 46%→39% |

### 11.4 Communication — Table III

| Scheme | Attribute Key | Hash Tuple | Ciphertext |
|:---|:---|:---|:---|
| PCH [17] | $(1+3k)\lvert\mathbb{G}\rvert+3\lvert\mathbb{G}_{p_1}\rvert$ | $3\lvert\mathbb{Z}_N^*\rvert$ | $3l\lvert\mathbb{G}\rvert+3\lvert\mathbb{G}_{p_1}\rvert+2\lvert\mathbb{G}_T\rvert+\lvert\mathbb{Z}_N^*\rvert$ |
| DPCH [25] | $2k\lvert\mathbb{G}\rvert$ | $6\lvert\mathbb{Z}_N^*\rvert$ | $3l\lvert\mathbb{G}\rvert+(1+l)\lvert\mathbb{G}_T\rvert+\lvert\mathbb{Z}_N^*\rvert$ |
| PCHA [19] | $(9+3k)\lvert\mathbb{G}\rvert$ | $5\lvert\mathbb{Z}_N^*\rvert$ | $(10+3l)\lvert\mathbb{G}\rvert+2\lvert\mathbb{Z}_N^*\rvert$ |
| PRHBS [33] | $(2+2k)\lvert\mathbb{G}\rvert$ | $(4+k)\lvert\mathbb{Z}_N^*\rvert$ | $(1+3l)\lvert\mathbb{G}\rvert+\lvert\mathbb{G}_T\rvert$ |
| **REBS** | $k\lvert\mathbb{G}\rvert$ | $3\lvert\mathbb{Z}_N^*\rvert$ | $2l\lvert\mathbb{G}\rvert+(1+l)\lvert\mathbb{G}_T\rvert+\lvert\mathbb{Z}_N^*\rvert$ |

### 11.5 Communication Results (Figs. 7–8)

| Setting | Result |
|:---|:---|
| Sizes | 512-bit $\mathbb{G}$, $\mathbb{G}_{p_1}$; 1024-bit $\mathbb{G}_T$, $\mathbb{Z}_N^*$ |
| l = 10 | ≈ 28,160 bits; −23.6% vs. DPCH, −23.5% vs. PCHA |
| l = 50 | −23.5% vs. DPCH |
| l = 100 | 227,840 bits |
| Breakdown (l = 50) | attribute keys 7.1%, hash tuple 2.7%, ciphertext **90.3%** |

## 12. Limitations (stated + relative to VeRedact-PQ)

- Hides only attribute **values**; names visible (authors' own limitation).
- Re-encryption (Delegate) overhead heavy for constrained verifiers (authors).
- **No traceability** of redactions yet (authors' future work) → **no audit/query mechanism**.
- **Not post-quantum** (RSA + composite-order pairings).
- **No blockchain deployment**: no end-to-end latency, throughput, consensus, or gas.
- **No threshold signing / batching**; single TR performs ChCld once attributes satisfied.

## 13. Conclusion

- REBS gives policy-hiding, time-limited, dynamically-verifiable transaction-level redaction for energy-trading consortium chains.
- Lower computation and ~23% lower communication than DPCH/PCHA; constant-time Verify and Update.
