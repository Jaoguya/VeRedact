# Scheme × Experiment Capability Matrix (VeRedact-PQ Evaluation, Exp. 1–5)

Source experiments: `overleaf/VeRedact.md` → *Performance Analysis*, Experiments 1–5.

## Papers in this folder

| # | File | Scheme | VeRedact ref |
|:--|:---|:---|:---|
| 1 | [1 summary](1_Improved-DCH_Li2025/summary.md) | Improved DCH (Li *et al.*, TC 2025) + re-implements **Jia DCH** | [30]; also benchmarks **[1] Jia** |
| 2 | [2 summary](2_ETCH_Liu2026/summary.md) | ETCH (Liu *et al.*, TDSC 2026) | **[27]** |
| 3 | [3 summary](3_EAQ-VRBC_Zhang2025/summary.md) | EAQ-VRBC (Zhang *et al.*, TrustCom 2025) + re-implements **VRBC/VRBCIA** | not cited; benchmarks **[13] VRBC** |
| 4 | [4 summary](4_REBS_Xue2025/summary.md) | REBS (J. Xue *et al.*, IoT-J 2025) | **[34]** (not [33]) |

Legend: **✓** directly testable (scheme has the mechanism *and* the paper reports comparable metrics) · **△** partially (only some configurations/sub-metrics, or needs porting) · **✗** not applicable (mechanism absent).

---

## 1. Summary Matrix

| Scheme | Exp 1 Latency & Throughput | Exp 2 Authorization Latency | Exp 3 Audit Efficiency | Exp 4 Verification Time | Exp 5 Gas |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Jia DCH [1]** (via Li 2025) | △ | △ | △ | △ | ✗ |
| **Improved DCH** (Li 2025) | △ | △ | ✗ | △ | ✗ |
| **ETCH [27]** (Liu 2026) | **△+** | △ | ✗ | △ | ✗ |
| **EAQ-VRBC** (Zhang 2025) | △ | ✗ | **✓** | **✓** | **✓** |
| **VRBC [13]** (via Zhang 2025) | △ | ✗ | **✓** | **✓** | **✓** |
| **REBS [34]** (J. Xue 2025) | △ | **△+** | ✗ | △ | ✗ |

- **Exp 3, 4, 5:** only **EAQ-VRBC / VRBC** give usable baseline numbers.
- **Exp 1:** no scheme measures throughput vs. arrival rate λ; **ETCH** comes closest (redaction latency vs. committee size + RTT).
- **Exp 2:** **REBS** is the only one with a policy-check stage; **DCH/ETCH** cover the threshold/committee stage.

---

## 2. Per-Experiment Detail

### Exp 1 — Redaction Latency & Throughput

VeRedact configs: (i) λ 50–1000 req/s · (ii) locality k 1–32 · (iii) committee (n,t) · (iv) ledger 10⁴–10⁶.

| Scheme | (i) λ / TP | (ii) k | (iii) (n,t) | (iv) ledger | Usable data |
|:---|:---:|:---:|:---:|:---:|:---|
| Jia DCH | ✗ | ✗ | ✓ | ✗ | Collision per party vs. t = 5…45 (flat, 0.23–14 ms by curve); one redaction per block only |
| Improved DCH | ✗ | ✗ | ✓ | ✗ | Same as above |
| ETCH | ✗ | ✗ | ✓ | ✗ | **End-to-end redaction < 0.38 s** at 33 redactors, RTT 300 ms (Fig. 6); Adapt vs. t = 3…33 |
| EAQ-VRBC / VRBC | ✗ | ✗ | ✗ | ✗ | Redact compute vs. #tx per block 50–500 (EAQ/AMVA17 ~2–4.5 ms, VRBC ~12–16 ms); single trusted SM, no committee |
| REBS | ✗ | ✗ | ✗ | ✗ | ChCld (Adapt) cost vs. #attributes only |

- **Action:** re-implement ETCH / DCH / REBS redaction paths on the Besu testbed to get λ-sweep numbers; none can be taken from the papers.
- **No scheme batches** → all behave like **VeRedact-PQ-NB** (B = 1); good as batching baselines.

### Exp 2 — Transaction Authorization Latency (Phases 3–4)

VeRedact stages: admission/SA-RLI lookup · requester signature · policy validation · PQZK verify · attestation · committee signatures; plus batch amortization and invalid ratio ρ.

| Scheme | Req. signature | Policy check | ZK verify | Committee / threshold | ρ rejection | Usable data |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| Jia DCH | ✓ (tx sigs checked) | ✗ | ✗ | ✓ (t-of-n approval + shares) | ✗ | Collision share cost vs. t |
| Improved DCH | — | ✗ | ✗ | ✓ | ✗ | Collision share cost vs. t |
| ETCH | △ (initiator's DS on the chameleon hash, checked at tx verification; no signed redaction request) | ✗ | ✗ | ✓ (t-of-n, CA aggregation) | ✗ | Adapt vs. t; KeyUpt |
| EAQ-VRBC / VRBC | ✗ | ✗ | ✗ | ✗ (trusted SM) | ✗ | — |
| REBS | ✓ ($Sig_{AMC}$ pairing check) | **✓** (LSSS policy + attribute keys) | ✗ | △ (multi-authority AVNs, not signing) | ✗ | AttrKeyGen / ChCld / Delegate vs. #attributes |

- **Policy-stage baseline:** REBS (attribute-policy satisfaction ≈ VeRedact "public policy validation").
- **Committee-stage baseline:** ETCH, DCH (per-redaction threshold ≈ **VeRedact-PQ-NB** "t signatures per request").
- **No scheme** has a PQZK stage or staged rejection → ρ sweep is VeRedact-only (ablation).

### Exp 3 — Audit Efficiency

VeRedact metrics: RAI insertion · epoch checkpoint · query resolution · evidence generation · response size; vs. RAI size, shards, result size 1–500; per query type.

| Scheme | Audit index | Query proof gen | Response size | Result-size sweep | Usable data |
|:---|:---:|:---:|:---:|:---:|:---|
| Jia DCH | △ RSA accumulator of redacted blocks | △ (mem/non-mem proof) | ✗ | ✗ | Mechanism only; no numbers in Li 2025 |
| Improved DCH | ✗ | ✗ | ✗ | ✗ | — |
| ETCH | ✗ | ✗ | ✗ | ✗ | — |
| **EAQ-VRBC** | ✓ RSA-accumulator revocation list | ✓ | ✓ (Table II formulas) | ✓ c = 50…500 | Audit proof gen **0.040–0.478 s**; query gen **~1.2–2 ms** |
| **VRBC** | ✓ BAT | ✓ | ✓ | ✓ c = 50…500 | Audit proof gen **3.16–8.78 s**; query gen 28–158 ms |
| REBS | ✗ | ✗ | ✗ | ✗ | — |

- **Direct match:** EAQ-VRBC's "#challenged blocks 50–500" ≈ VeRedact's $\lvert\mathcal{R}_{Q_j}\rvert$ 1–500.
- **Index-size proxy:** EAQ-VRBC/VRBC query cost vs. queried block index 100–51,100 is the closest counterpart to VeRedact's RAI size sweep ($10^3$–$10^6$); EAQ-VRBC query gen stays flat (~1.2–2 ms), VRBC grows 28→158 ms.
- **Query types:** EAQ-VRBC/VRBC support only integrity + freshness-style queries; authorization/policy/scope queries are VeRedact-only.

### Exp 4 — Verification Time

VeRedact: normal vs. deep audit; result size 1–500; distinct batches 1–100; **single-redaction verification vs. compared schemes**.

| Scheme | Audit-response verify | Single-redaction verify | Usable data |
|:---|:---:|:---:|:---|
| Jia DCH | ✗ | ✓ | Verify 3.40 / 11.93 / 14.14 ms (Type A/E/F, t = 5) |
| Improved DCH | ✗ | ✓ | Verify 2.14 / 9.22 / 13.72 ms |
| ETCH | ✗ | ✓ | Verify ~3 ms (secp256k1), ~51.8% below VDCH |
| **EAQ-VRBC** | ✓ | ✓ | Audit verify **2.7–32.5 ms** (c = 50…500); query verify ~7.5 ms |
| **VRBC** | ✓ | ✓ | Audit verify **3.65–4.14 s**; query verify 2.9–3.7 s |
| REBS | ✗ | ✓ | ChVer ~3 ms, constant in #attributes |

- **All schemes** can join the "single redaction verification" comparison.
- **Only EAQ-VRBC / VRBC** can be compared on result-size sweeps.
- **Shared-evidence analogue:** EAQ-VRBC aggregates non-membership witnesses and batch-verifies them (Alg. 2–3), comparable in spirit to VeRedact verifying shared ABRRR evidence once per batch ($\lvert\Omega^B_{Q_j}\rvert$ sweep).

### Exp 5 — Blockchain Gas Consumption

| Scheme | On-chain contract | Gas reported | Usable data |
|:---|:---:|:---:|:---|
| Jia DCH / Improved DCH | ✗ | ✗ | — |
| ETCH | ✗ (Bitcoin-style prototype) | ✗ | — |
| **EAQ-VRBC** | ✓ Ethereum Ropsten | ✓ | Setup 71,768 · Upload 254,526 · Redact 104,788 · Query 132,913 · Audit 158,336 Gwei |
| **VRBC** | ✓ | ✓ | Setup 81,311 · Upload 81,025 · Redact 81,037 · Query 145,671 · Audit 157,225 Gwei |
| REBS | ✗ | ✗ | — |

- **Caveat:** EAQ-VRBC reports **Gwei**, VeRedact measures **gas units** on Besu QBFT → re-measure, don't copy.
- Non-contract schemes need a minimal anchoring contract written by you to be comparable.

---

## 3. Issues Found in `VeRedact.md` (decisions for you)

| # | Issue | Where |
|:--|:---|:---|
| 1 | **Missing PDF:** Wang *et al.* [17] (quantum-resistant) is a compared scheme but not in `Scheme/` | Compared Schemes |
| 2 | **Wrong Xue:** compared list says Xue *et al.* **[33]** (L. Xue, Main–Auxiliary, TDSC 2026); dropped PDF is J. Xue **[34]** (REBS). [33] PDF also missing | Compared Schemes |
| 3 | **Jia [1] vs. Li [30]:** dropped PDF is Li's *revisit*, which shows Jia's DCH is **insecure**; consider comparing against Improved DCH or noting the attack | Compared Schemes, Table I |
| 4 | **Table I overclaims REBS [34]** "Verifiable Auditing ✓" — REBS has no audit/query mechanism; traceability is its future work | Table I |
| 5 | **Table I overclaims Liu [27]** "Scalable/Batch ✓" — ETCH has no batching; each tx redacted individually | Table I |
| 6 | **EAQ-VRBC not cited** but is the only paper giving VRBC [13] baseline numbers for Exp 3–5 | References |
