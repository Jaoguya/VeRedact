# Redactable Blockchain From Decentralized Chameleon Hash Functions, Revisited

| Field | Value |
|:---|:---|
| **Authors** | Cong Li, Qingni Shen, Zhonghai Wu (Peking University) |
| **Venue** | IEEE Transactions on Computers, vol. 74, no. 6, pp. 1911–1920, June 2025 |
| **DOI** | 10.1109/TC.2025.3544878 |
| **Source PDF** | `Redactable_Blockchain_From_Decentralized_Chameleon_Hash_Functions_Revisited.pdf` |
| **Short name** | **Improved DCH** (Li *et al.*), cryptanalysis + fix of Jia *et al.* DCH [TIFS 2022] |
| **Paper type** | Cryptanalysis + primitive design (no full system/platform) |
| **Keywords** | Cryptanalysis, redactable blockchain, decentralization, chameleon hash function |

> Note on citation: VeRedact-PQ cites "the decentralized chameleon-hash scheme of Jia *et al.* [1]". This PDF is **Li *et al.*'s revisit** of Jia *et al.*: it breaks Jia's DCH and proposes Improved DCH. Both DCH (Jia) and Improved DCH (Li) are implemented and benchmarked here.

---

## 1. Abstract (summary)

- Redactable blockchains fall into **centralized** (one trapdoor holder, single point of failure) and **decentralized** (many nodes cooperate, but slow or need a trusted party).
- Jia *et al.* proposed a **decentralized chameleon hash (DCH)** with threshold redaction, traceability, and consistency checks.
- This paper shows a **concrete attack**: after one legitimate redaction at height *h*, any single malicious full node can forge further redactions at that height **without other nodes' approval**.
- Fix: a new **BLS-based chameleon hash** whose collision resistance reduces to EU-CMA of BLS, lifted to a threshold **Improved DCH**.
- Improved DCH has efficiency comparable to DCH and **50% smaller randomness**.

## 2. Problem Statement

- Jia's DCH only achieves **key-exposure freeness (KEF)**: no collisions for labels never queried to the collision oracle.
- In Jia's chain, all versions of a block at one height **share the same label** $u = H(g^s, m)$ so the hash stays constant.
- A redacted block = the label has been queried → adversary can derive more collisions for that label.
- **Root cause:** KEF-level collision resistance is insufficient for redactable blockchains.

## 3. Contributions

1. Identify the flaw in Jia *et al.*'s DCH and give a concrete attack.
2. New chameleon hash (CH) with standard collision resistance, reducible to BLS EU-CMA; build **Improved DCH** on it.
3. First detailed theoretical cost analysis of DCH vs. Improved DCH, plus a PBC implementation.

## 4. Related Work (as positioned by the paper)

| Setting | Works | Noted weakness |
|:---|:---|:---|
| Centralized CH | Ateniese [1], Derler F-CollRes [2], Li–Liu tagged lattice CH [3], Astrizi preimage CH [9], Huang TUCH/LRRS [10], Jia sCHRS [11], Xu k-time [12] | Single trapdoor holder |
| Policy-based CH | Derler PCH [13], accountable PCH [14,15], revocable PCH [16,17], ReTrace [18], online/offline PCH [19] | Central attribute authority |
| Decentralized | Deuber voting [4] | Voting slow, scales with #tx |
| | Huang RCB [5] | (n,n) only; broken by Gao [7] |
| | Zhang Re-chain [6] | Trusted party in trapdoor gen, no traceability |
| | Jia DCH [8] | **Broken in this paper** |
| | Wu VDCH [26], MAPCH [27], DPCH [30], DACH [32] | — |

## 5. Preliminaries

- **Symmetric bilinear pairing** $e: \mathbb{G}\times\mathbb{G}\to\mathbb{G}_T$, prime order $p$, generator $g$.
- Bilinearity $e(u^a,v^b)=e(u,v)^{ab}$; non-degeneracy $e(g,g)\neq 1$; efficiently computable.
- Lagrange coefficient: $\lambda_i=\prod_{j\ne i}\frac{ID(P_j)}{ID(P_j)-ID(P_i)} \bmod p$.

### 5.1 Jia *et al.*'s DCH (reviewed)

- **KeyGen** (Pedersen-style DKG): each $P_i$ picks $f_i(x)=\sum_{j=0}^{t-1}a_{i,j}x^j$, sends shares + commitments; public key $g^s=\prod_j g^{a_{j,0}}$, share $s_i=f(ID(P_i))$.
- **Hash**$(g^s,m)$: $u\leftarrow H(g^s,m)$, random $e$; $h=g^e u^m$, randomness $r=(g^e, g^{se})$.
- **Verify**: $g^{e}u^{m}=g^{e'}u^{m'}$ and $(g,g^s,g^{e'},g^{se'})$ is a DH tuple.
- **Collision**: $g^{e'}=g^e u^{m-m'}$; each $P_i$ sends $\eta_i=(g^{e'})^{\lambda_i s_i}$; $g^{se'}=\prod\eta_j$.

### 5.2 Jia's Redactable Blockchain

- **Block header:** `(prev_hash, last_hash, m_root, acc, r)`; `acc` is an **RSA accumulator** over hashes of redacted blocks.
- **Redaction:** full node $P$ builds `req = (last_hash', addr_tx, tx', m_root')`; if $t' \ge t$ nodes approve, they run DCH.Collision; $P$ packs `data = (addr_tx, hash_tx', m_root', last_hash', r')` into $tx_{req}$; after on-chain, every node rewrites the header.
- A block can be redacted **only once** (checked via `acc`).
- **Consistency check:** client queries $(h, hash_B)$; node returns block + RSA-accumulator (non-)membership proof.

## 6. Attack on Jia *et al.*

### 6.1 Collision derivation without trapdoor

Given one collision $(m,r=(g^e,g^{se}))$, $(m',r'=(g^{e'},g^{se'}))$ with the same $h$:

$$h=g^e u^m=g^{e'}u^{m'}\;\Rightarrow\; g^{se}u^{sm}=g^{se'}u^{sm'}$$

$$u^s=\left(g^{se'}/g^{se}\right)^{\frac{1}{m-m'}}$$

For any new $m''$:

$$g^{e''}=g^{e}u^{m-m''},\qquad g^{se''}=g^{se}(u^s)^{m-m''}$$

### 6.2 Concrete attack flow

1. Honest node legitimately redacts block ① at height *h* → block ③ (threshold approval, $tx_{req0}$ in block ②).
2. Malicious node $\hat P$ uses header₀, r₀ and the published collision to compute a fresh $\hat r$ for arbitrary $\hat{tx}$ **alone**.
3. $\hat{tx}_{req}$ passes DCH.Verify; it gets packed, and all nodes rewrite to block ⑤.
4. `acc` insertion still happens → the illegitimate redaction **passes the consistency check**.

## 7. Proposed Scheme

### 7.1 Base Chameleon Hash (BLS-based)

| Algorithm | Definition |
|:---|:---|
| PGen | $pp=(\mathcal{D},H)$, $H:\{0,1\}^*\to\mathbb{G}$ |
| KeyGen | $sk=x\in\mathbb{Z}_p$, $pk=y=g^x$ |
| Hash | random $\xi$; $h=H(m)g^{\xi}$, $r=y^{\xi}$ |
| Verify | $e(h/H(m),\,y)\overset{?}{=}e(g,\,r)$ |
| Collision | check Verify; $r'=r\cdot(H(m)/H(m'))^{x}$ |

- Design idea: collision resistance → **EU-CMA of BLS** ($r' = r\cdot\sigma/\sigma'$).
- Achieves standard collision resistance + indistinguishability (not "full" as in Chan *et al.* ACM AsiaCCS'24); no SSE-NIZK.

### 7.2 Improved DCH

- **KeyGen:** same DKG as Jia; $pk=y=g^x$, $x=\sum_j a_{j,0}$, share $x_i=f(ID(P_i))$.
- **Hash / Verify:** same as base CH.
- **Collision:** each $P_i$ sends $\eta_i=(H(m)/H(m'))^{\lambda_i x_i}$; $r'=r\cdot\prod_j\eta_j$.
- The exponent $\xi$ is hidden inside $r$ → hash can't be recomputed from $(pk,m,r)$ → header field `rand` extended to **`curr_hash&rand`**.

### 7.3 Correctness

$$e(h/H(m'),y)=e(g^{\xi}H(m)/H(m'),g^x)=e(y^{\xi}(H(m)/H(m'))^x,g)=e(g,r')$$

## 8. Security Analysis

- **Collision resistance (via existing collisions):** reduces to base CH; no PPT adversary finds a collision for a fresh message even with oracle access → attack of §6 blocked.
- **Collision resistance (via trapdoor):** Shamir sharing; $\le t-1$ shares reveal nothing about $x$ or $(H(m)/H(m'))^x$.
- **Indistinguishability:** analogous to base CH (proof in appendix, not in this PDF).
- **Not covered:** post-quantum security (pairing/DL-based), policy control, auditing, replay/freshness.

## 9. Performance Evaluation

### 9.1 Theoretical Cost (Table I)

| Algo./Component | DCH [Jia] | Improved DCH |
|:---|:---|:---|
| KeyGen | $(t^2+t)E$ | $(t^2+t)E$ |
| Hash | $3E+H_G$ | $2E+H_G$ |
| Verify | $2E+V+H_G$ | $2P+H_G$ |
| Collision | $2E+H_G$ | $E+2H_G$ |
| $\lvert pk\rvert$ | $\lvert\mathbb{G}\rvert$ | $\lvert\mathbb{G}\rvert$ |
| $\lvert sk\rvert$ | $\lvert\mathbb{Z}_p\rvert$ | $\lvert\mathbb{Z}_p\rvert$ |
| $\lvert h\rvert$ | $\lvert\mathbb{G}\rvert$ | $\lvert\mathbb{G}\rvert$ |
| $\lvert r\rvert$ | $2\lvert\mathbb{G}\rvert$ | $\lvert\mathbb{G}\rvert$ |

*E: exponentiation in G; H_G: hash-to-G; V: DH-tuple check; P: pairing.*

### 9.2 Experimental Setup

| Item | Value |
|:---|:---|
| Library | PBC 0.5.14, C++17 |
| Curves | Type A (\|q\|=512, \|r\|=160), Type E (\|q\|=1024, \|r\|=160), Type F (\|r\|=160) |
| Machine | Intel i5-13600KF 3.5 GHz ×14, 4 GB RAM (WSL), Ubuntu 22.04.3 |
| Repetitions | 1000 runs, averaged |
| Participants | $t=5$ (Table II); $t=5\ldots45$ step 4 (Fig. 2) |
| Blockchain platform | **None** (primitive-level only) |

### 9.3 Results — Table II (ms, per participant, t = 5)

| Pairing | Scheme | KeyGen | Hash | Verify | Collision |
|:---|:---|---:|---:|---:|---:|
| Type A | DCH [Jia] | 19.48 | 3.52 | 3.40 | 2.66 |
| Type A | Improved DCH | 19.11 | 3.49 | 2.14 | 3.45 |
| Type E | DCH [Jia] | 41.28 | 10.47 | 11.93 | 9.19 |
| Type E | Improved DCH | 41.18 | 10.35 | 9.22 | 14.32 |
| Type F | DCH [Jia] | 37.19 | 0.64 | 14.14 | 0.44 |
| Type F | Improved DCH | 37.18 | 0.46 | 13.72 | 0.23 |

### 9.4 Results — Scaling with t (Fig. 2)

- **KeyGen:** quadratic in *t*; at $t=45$ ≈ 1280 ms (A), 2770 ms (E), 1420 ms (F).
- **Collision:** flat in *t*; max–min gap ≤ 0.15 / 0.45 / 0.08 ms (DCH) and 0.18 / 0.6 / 0.08 ms (Improved DCH).
- **Verify:** Improved DCH faster by 1.26 / 2.71 / 0.42 ms (A/E/F).
- **Hash on Type F:** 28.13% faster.

## 10. Limitations (relative to VeRedact-PQ)

- **Not post-quantum** (pairing-based).
- **No end-to-end redaction latency/throughput**, no consensus, no smart contracts, no gas.
- **No policy / ZK verification**, no request authentication pipeline.
- **No auditing/query** mechanism beyond Jia's RSA-accumulator consistency check (not re-evaluated here).
- **One redaction per block** in the underlying Jia chain design.

## 11. Conclusion

- Jia's DCH is insecure after the first redaction at a height.
- Improved DCH (BLS-based) fixes it with essentially the same cost and half the randomness size.
