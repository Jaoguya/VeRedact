# Enhancing Redactable Blockchain With Robust and Efficient Threshold Redaction

| Field | Value |
|:---|:---|
| **Authors** | Zhaoman Liu, Biming Zhou, Yunlei Zhao (Fudan University) |
| **Venue** | IEEE Transactions on Dependable and Secure Computing, vol. 23, no. 2, pp. 3238–3251, Mar./Apr. 2026 |
| **DOI** | 10.1109/TDSC.2025.3634512 |
| **Source PDF** | `Enhancing_Redactable_Blockchain_With_Robust_and_Efficient_Threshold_Redaction.pdf` |
| **Short name** | **ETCH** (Enhanced Threshold Chameleon Hash), Liu *et al.* — VeRedact-PQ ref [27] |
| **Paper type** | Primitive design + Bitcoin-based prototype |
| **Code** | https://github.com/Water-lzm/ETCH-based-Redaction-Blockchain |
| **Keywords** | Redactable blockchain, threshold chameleon hash, enhanced collision resistance, robust, key update |

---

## 1. Abstract (summary)

- Proposes **ETCH**: redaction only when ≥ *t* redactors jointly produce trapdoor shares.
- **Enhanced collision resistance (ECR):** no new collisions even after seeing prior collisions.
- **Periodic trapdoor-share refresh** (proactive secret sharing) with the hash key unchanged.
- Cost vs. prior threshold CH: **−50% Hash/Verify**, **−22.26% Adapt**.
- Bitcoin-based prototype: low-latency redaction and **reduced chain growth**.

## 2. Problem Statement

| Problem | Prior schemes affected |
|:---|:---|
| **Weak collision resistance** — new collisions computable after one redaction | TCH [11], Jia DCH [17], VDCH [18] (all built on Chen *et al.* [33]) |
| **Trapdoor leakage / trusted dealer** | Zhang–Ni [16], Re-chain [24] |
| **(n,n) or (t,t) threshold** — one offline node blocks redaction | TCH [11], DCH [17] |
| **Key fatigue** — long-lived shares eventually leak | All prior threshold CH |

## 3. Contributions

1. **ECR threshold CH** based on Ateniese–de Medeiros trapdoor commitment (twin Nyberg–Rueppel); fully decentralized DKG, trapdoor never known to any node.
2. **KeyUpt**: proactive share renewal without changing the trapdoor/hash key.
3. **Chain integration:** initiator signs the **chameleon hash** instead of the tx body → signature survives redaction; Merkle leaf hash replaced by ETCH.
4. Experiments vs. TCH, DCH, VDCH + a prototype system.

## 4. Related Work — Table I (paper's comparison)

| Type | Scheme | Setting | Tools | Trapdoor Gen. | Redactor | Level | KeyUpdate | Collision Res. |
|:---|:---|:---|:---|:---|:---|:---|:---:|:---|
| Voting | [6] µchain | Permissionless | Voting, MPC | N/A | All users | Transaction | ✗ | N/A |
| Voting | [7] Deuber | Permissionless | Voting | N/A | All users | Tx (delete only) | ✗ | N/A |
| Voting | [8] Reparo | Permissioned/less | Voting | N/A | All users | Tx (delete only) | ✗ | N/A |
| Voting | [9] Marsalek | Permissionless | Voting | N/A | All users | Block | ✗ | N/A |
| CH | [5] Ateniese | Permissioned/less | CH, MPC | Centralized / Decentralized | Central authority / (t,n) | Block | ✗ | Enhanced CR |
| CH | [10] Derler PCH | Permissioned/less | CH, CP-ABE | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [20] ReTRACe | Permissioned | CHET, CP-ABE, Group Sig | Centralized | Authorized users | Transaction | ✗ | Revocation CR |
| CH | [13] Tian | Permissioned | CHET, CP-ABE, Sig | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [14] Xu | Permissioned | CHET, CP-ABE, Sig | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [15] Tian | Permissionless | DPSS, KP-ABE, Sig | Centralized | Authorized users | Transaction | ✗ | Adaptive CR |
| CH | [21] MAPCH | Permissioned | CHET, CP-ABE | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [22] DPCH | Permissioned | CHET, CP-ABE, Sig | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [23] DACH | Permissioned | CHET, CP-ABE, LSSS | Centralized | Authorized users | Transaction | ✗ | Insider CR |
| CH | [11] TCH (Huang) | Permissioned | CH, Sig | Distributed | (n,n) | Transaction | ✗ | Weak CR |
| CH | [24] Re-chain | Permissioned | CH | Distributed | (t,n) | Block | ✗ | Weak CR |
| CH | [17] Jia DCH | Permissionless | CH, MPC | Distributed | (t,n) | Transaction | ✗ | Weak CR |
| CH | [18] VDCH | Permissioned | CH, Voting, MPC | Distributed | (t,n) | Transaction | ✗ | Weak CR |
| CH | **ETCH (Ours)** | Permissioned | CH, Signature | Distributed | (t,n) | Transaction | ✓ | **Enhanced CR** |

## 5. Preliminaries

### 5.1 Trapdoor Commitment (base CH)

| Algorithm | Definition |
|:---|:---|
| Setup | safe prime $p=2q+1$, $g$ of order $q$, $H:\{0,1\}^*\to\mathbb{Z}_q$ |
| HGen | $tk=x\leftarrow\mathbb{Z}_q$, $hk=y=g^x$ |
| Hash | random $(r,w)$; $e=H(m,r)$; $h=r\,y^{e}g^{w}\bmod p$ |
| HCol | random $k'$; $r'=h/g^{k'}$; $e'=H(m',r')$; $w'=k'-e'x\bmod q$ |

- Correctness: $r'y^{e'}g^{w'}=h/g^{k'}\cdot g^{xe'}\cdot g^{k'-e'x}=h$.
- **Enhanced CR:** no collision for $h^*$ unless a collision for that same $h^*$ was revealed.
- **Semantic security:** $H[m\mid h]=H[m]$.

### 5.2 Proactive Secret Sharing (Herzberg *et al.*)

- **Share renewal:** each node adds shares of a random zero-constant polynomial $Q_i(x)$; secret unchanged.
- **Share recovery:** lost share reconstructed via polynomials $R_i(x)$ with $R_i(r)=0$.

### 5.3 Digital Signature

- DS = (KeyGen, Sign, Verify), generic EU-CMA.

## 6. System Model

- **Initiator** (fully trusted): creates and signs transactions; may go offline afterwards.
- **Redactors** (semi-trusted, trustees): hold trapdoor shares; ≥ *t* collaborate to redact.
- **Commitment Aggregator (CA)** (optional, semi-trusted): aggregates collision shares to cut communication; ETCH can also run fully decentralized.

## 7. Threat Model

- Initiator fully trusted.
- Redactors/external users **semi-trusted**: follow protocol but try to deduce trapdoor from their share, others' hash-key shares, tx data, collisions.
- Collusion allowed up to **< t** redactors.
- External users treated as a special case of semi-trusted redactors.

## 8. Main Phases

1. **Initialization** — initiator creates signing key pair; redactors run ETCH.KeyGen.
2. **Transaction Creation** — initiator hashes TX with ETCH, signs $h$.
3. **Transaction Redaction** — ≥ *t* redactors run ETCH.Adapt → new $(r',w')$.
4. **Key Update** — periodic ETCH.KeyUpt.

## 9. ETCH Construction

$\Pi_{ETCH}=(\text{Setup, KeyGen, Hash, Verify, Adapt, KeyUpt})$

- **Setup:** safe prime $p=2q+1$; $g$ generates quadratic residues $Q_p$; $H:\{0,1\}^*\to\{0,1\}^\tau$.
- **KeyGen (Pedersen DKG):**
  1. $P_i$ samples $f_i(x)=a_{i0}+\dots+a_{i(t-1)}x^{t-1}$, publishes $C_i=(\phi_{i0},\dots,\phi_{i(t-1)})$, $\phi_{ij}=g^{a_{ij}}$.
  2. Sends $(j,f_i(j))$ privately to $P_j$.
  3. $P_i$ checks $g^{f_j(i)}=\prod_k\phi_{jk}^{i^k}$; sets $s_i=\sum_j f_j(i)$, $y_i=g^{s_i}$, hash key $y=\prod_j\phi_{j0}$.
- **Hash:** random $(r,w)\in\mathbb{Z}_p^*\times\mathbb{Z}_q^*$; $e=H(m,r)$; $h=r\,y^{e}g^{w}\bmod p$.
- **Verify:** recompute $e$; accept iff $h=r\,y^{e}g^{w}\bmod p$.
- **Adapt** (≥ *t* parties, via CA):
  1. $P_i$: random $k_i$, sends $K_i=g^{k_i}$.
  2. CA: $K=\prod K_i$; sends $K,m'$.
  3. $P_i$: $r'=h/K$, $e'=H(m',r')$, $w_i=k_i-e'\lambda_i s_i$ (Lagrange $\lambda_i=\prod_{j\ne i}\frac{j}{j-i}$).
  4. CA: $w'=\sum w_i$; output $(r',w')$.
- **KeyUpt** (period $T$):
  1. $P_i$ picks $\delta_i(x)=\delta_{i1}x+\dots+\delta_{i(t-1)}x^{t-1}$ ($\delta_i(0)=0$), publishes $g^{\delta_{ik}}$.
  2. Sends $z_{ij}=\delta_i(j)$ to $P_j$.
  3. $P_j$ verifies $\prod_k (g^{\delta_{ik}})^{j^k}=g^{z_{ij}}$; updates $s_i^{(T)}=s_i^{(T-1)}+\sum_j\delta_j(i)$.
  - Trapdoor $s$ and hash key $y$ **unchanged**.

## 10. Security Analysis

- **Indistinguishability** (ROM): fresh-hash and adapted $(h,r,w)$ distributions identical except negligibly.
- **Enhanced Collision Resistance:** reduction to twin Nyberg–Rueppel signature, DL in generic group model; adversary holds < *t* shares per period (can be different sets across periods).
- **Semantic security:** uniform $w$ makes $h$ independent of $m$.
- **Not covered:** post-quantum security, policy compliance, request authentication, replay/freshness, auditing.

## 11. ETCH-Based Redactable Blockchain

- **Tx structure:** adds randomness pair $(r,w)$; signature $\sigma_{TX}=\text{DS.Sign}(sk_s,h)$ over the chameleon hash.
- **Block structure:** **Merkle leaf hash = ETCH**, so root and block links survive tx redaction.
- **Tx verification:** recompute ETCH hash, then DS.Verify.
- **Redaction:** redactor invites others → Adapt → embeds $(r',w')$ in $TX'$; signature unchanged; nodes verify and replace $TX$ with $TX'$.
- **Share update:** periodic KeyUpt; hash key constant so initiators never re-fetch it.
- Consensus and block propagation unchanged (PoW/PBFT).

## 12. Performance Evaluation

### 12.1 Complexity — Table IV

| Scheme | KeyGen | Hash | Adapt | Verify |
|:---|:---|:---|:---|:---|
| DCH [17] | $(t^2+t+1)T_E+(t-1)^2T_M$ | $3T_E+T_M+T_H$ | $2T_E+tT_M+T_H$ | $T_E+T_M+T_H$ |
| TCH [11] | $2T_E$ | $3T_E+T_M+2T_H$ | $3T_E+2T_M+3T_H$ | $T_E+T_M+2T_H$ |
| VDCH [18] | $(nt+2)T_E+(n-1)(t-1)T_M$ | $3T_E+T_M+3T_H$ | $T_{INV}+3T_E+(2t+1)T_M+2T_H$ | $2T_E+T_M+3T_H$ |
| **ETCH** | $(nt+1)T_E+(n-1)(t-1)T_M$ | $2T_E+2T_M+T_H$ | $T_{INV}+2T_E+T_M+T_H$ | $2T_E+2T_M+T_H$ |

*t: threshold; n: #users; T_E: exponentiation; T_M: multiplication; T_H: hash; T_INV: inverse.*

### 12.2 Size — Table V

| Scheme | sk | h | Randomness | Execution | Threshold |
|:---|:---|:---|:---|:---|:---|
| DCH [17] | $\lvert\mathbb{Z}_q^*\rvert$ | $\lvert\mathbb{G}\rvert$ | $2\lvert\mathbb{G}\rvert$ | Parallel | (t,t) |
| TCH [11] | $\lvert\mathbb{Z}_q^*\rvert$ | $\lvert\mathbb{G}\rvert$ | $2\lvert\mathbb{G}\rvert$ | Sequential | (t,t) |
| VDCH [18] | $\lvert\mathbb{Z}_q^*\rvert$ | $\lvert\mathbb{G}\rvert$ | $3\lvert\mathbb{G}\rvert$ | Parallel | (t,n) |
| **ETCH** | $\lvert\mathbb{Z}_q^*\rvert$ | $\lvert\mathbb{Z}_p^*\rvert$ | $\lvert\mathbb{Z}_p^*\rvert+\lvert\mathbb{Z}_q^*\rvert$ | Parallel | (t,n) |

### 12.3 Primitive Benchmark Setup

| Item | Value |
|:---|:---|
| Machine | AMD R5-5600U 2.3 GHz, 6 GB RAM (XiaoxinAir 14+) |
| Group / hash | secp256k1, SHA-256 |
| Repetitions | 1000, averaged |
| Threshold *t* (Fig. 4) | 3 → 33 |
| Compared | TCH, DCH, VDCH |

### 12.4 Primitive Results — Fig. 4 (approx. read from plots, t = 3…33)

| Stage | TCH | DCH | VDCH | ETCH |
|:---|---:|---:|---:|---:|
| KeyGen (log-scale) | lowest (sequential, no share check) | grows ~quadratic | grows ~quadratic | grows ~quadratic |
| Hash (ms, flat in t) | ~8 | ~6 | ~6 | **~3** |
| Adapt (ms, at t = 33) | ~108 | ~130 | ~200 | **~83** |
| Verify (ms, flat in t) | ~8.5 | ~5.5 | ~5.5 | **~3** |

- Stated gains: **~50%** Hash, **22.26%** Adapt (vs. TCH), **51.78%** Verify (vs. VDCH).

### 12.5 Prototype Setup — Table VI

| Parameter | Value |
|:---|:---|
| Base code | Karim Boubouh's redactable-blockchain benchmark (Bitcoin-based) |
| Block interval | 10 min |
| Avg. block propagation delay | 0.42 s |
| Transaction throughput | 5 TPS |
| Block size | 1 MB |
| Transaction size | 630 B |
| Number of nodes | 100 |
| Network RTT | 20 / 50 / 100 / 200 / 300 ms |

### 12.6 Prototype Results

| Experiment | Metric | Result |
|:---|:---|:---|
| Fig. 5a — per-hash cost | ETCH vs. SHA-256 | ETCH ≈ **1.8×** SHA-256, still ms-range |
| Fig. 5b — block creation | Time vs. #redactors | Negligible impact vs. 10-min interval |
| Fig. 6 — redaction latency | vs. RTT and #redactors (5→33) | **< 0.38 s** at RTT = 300 ms, 33 redactors; linear in #redactors |
| Fig. 7 — chain growth | Redaction vs. append-update, intervals 720/840/960/1000 s | Chain size **−21.58%** (720 s), **−11.91%** (960 s) |

## 13. Limitations (relative to VeRedact-PQ)

- **Not post-quantum** (DL-based).
- **No throughput vs. arrival rate**, no batching, no latency breakdown by phase.
- **No policy/ZK checks**; initiator fully trusted; no requester authentication pipeline or replay handling.
- **No audit index / query / verification of redaction history.**
- **No smart contracts / gas** (Bitcoin-style prototype).
- Dynamic join/leave of redactors left as future work.

## 14. Conclusion

- ETCH gives (t,n) decentralized, enhanced-CR threshold redaction with proactive share refresh.
- Faster Hash/Verify/Adapt than TCH/DCH/VDCH; practical sub-second redaction in a Bitcoin-like prototype.
