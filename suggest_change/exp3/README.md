# Exp. 3 suggested changes

Issue #7. Three parts: **step 1**, the verdict (why we lose); **step 2**, a redesigned experiment (one panel,
end-to-end audit cost); **step 3**, four changes — two implementation, two protocol — because step 2 alone leaves
the response at 67 MB and the auditor at 14.6 s.

Everything below is read from release `run-2026-11-03` unpacked into `Benchmark/results/`. Reproduce every table:

```bash
python Other/analysis/exp3_step1.py
```

All numbers are at the drawn `records_per_batch = 64` (`veredact.reference_batch`) and, where one point is
quoted, at n_Q = 10^4. Primitives (Exp. 0 medians): T_V = 0.0298 ms (ML-DSA-65 verify),
**T_CH = 1.0763 ms (SIS-PQCH hash)**, T_H = 0.0013 ms. ML-DSA-65 signature = 3,309 B.

## Step 1 — Why we lose

### The verdict table

| Point / curve | Win/lose (×) | Cause | Kind | Evidence |
|---|---|---|---|---|
| (a) generation vs Scheme [1] | **win 51×** (49.8 ms vs 2,537 ms) | S1 builds a block + RSA-3072 accumulator membership witness per record; we build one query-scoped RAI multiproof | — | table A; `s01_improved_dch/adapter.py:230-244` |
| (a) generation vs Scheme [13] | **win 57,000×** (49.8 ms vs 2,848 s) | S13 builds one RSA-3072 **non-membership** witness per *challenged block*, each O(history) over the 11,853-redaction accumulator: **7.0 s per witness**, up to the ledger's 391 blocks | — | table E (implied blocks 10 / 68 / 288 / 405); `s13_eaq_vrbc/adapter.py:161`, `nonmem_create_raw` |
| **(b) response size vs Scheme [13]** | **lose 3,163×** (67.08 MB vs 21.2 KB) | S13 returns one aggregate proof `((V,S), μ, w)` for the whole challenged set; we return per-record evidence. **90.5 % of our bytes are ML-DSA-65 signatures** | baseline does less (one decision, no attribution) + PQ cost (3,309 B/signature vs 32–48 B classical) | table B; `veredact.py:487-513`; `s13_eaq_vrbc/adapter.py:174-186` |
| **(b) response size vs Scheme [1]** | **lose 13.5×** (6,708 vs 496 B per record) | per record we ship α_i (3,309 B, 49.3 % of the response); per transition we ship σ_b' (3,309 B, 37.4 %). S1 ships msg + 48 B BLS randomness + 384 B RSA witness | PQ cost + implementation (σ_b' is already anchored, see step 3 O3) | table B |
| **(c) verification vs Scheme [13]** | **lose 227×** (14.56 s vs 64.2 ms) | S13 runs **one** `audit_verify` and applies the one boolean to every record (`{i: ok for i in range(...)}`); its cost is flat in n_Q. We decide each record independently | baseline does less | table A, table E (`decisions returned` = 1); `s13_eaq_vrbc/adapter.py:170,185` — and Fig. 6(c) shows the same aggregate decision as false rejections |
| (c) verification vs Scheme [1] | **win 2.4×** (14.56 s vs 35.45 s) | S1 verifies an Improved-DCH collision (2 pairings, T_CV^c = 2.31 ms) and an RSA-3072 membership exponentiation per record | — | table A; Exp. 0 `T_CV^c` |
| **(c) SAVER only 1.42× Shared-Evidence** | win, but far below the claim | sharing only reaches the authorization node (10,000 → 157). The transition and checkpoint nodes barely share (10,000 → 7,571, **1.32 records per transition**) and the request node can never share. Node ratio 1.58, time ratio 1.42 | workload doesn't use our mechanism — the same root cause as Exp. 1's weak SFMR sharing: CORA rarely puts two requests of a round in one batch | table C |
| **(c) 72 % of verification is one primitive** | — | `verify_state_ms` = 11.03 s of 15.29 s: `c.ch_verify` recomputes the SIS chameleon hash once per transition. T_CH = 1.076 ms is **36× an ML-DSA verify** | PQ cost | table D1/D2; `veredact.py:665-678` |
| **(c) 6.3 s of 15.3 s is the SAVER cache key** | — | χ(v) is recomputed **per record** over the node's *full* evidence — the five committee ML-DSA signatures (16.5 KB) for χ_auth, the raw PQCH value and randomness arrays for χ_tr, σ_b' for χ_cp — before the sharing check can fire. Excess over the crypto model: 0.288 + 0.204 + 0.081 + 0.053 = **0.626 ms per record** | implementation | table D2 `excess_ms_per_record`; `veredact.py:583-619` (`chi_auth`, `chi_tr`, `chi_cp` inside the per-record loop) |
| (c) order Per-Record > Shared-Evidence > VeRedact-PQ | holds | 20.49 s > 20.63 s ≈ 20.5 s > 14.56 s. Per-Record and Shared-Evidence are within noise of each other (both verify 40,000 nodes); only the response size separates them (244.5 MB vs 67.1 MB) | — | tables A and C |

Kinds used: *baseline does less · PQ cost · unfair harness · workload doesn't use our mechanism.*

### The one sentence a reviewer will write

> "Scheme [13] answers the same query in 64 ms with a 21 KB response; VeRedact-PQ needs 14.6 s and 67 MB."

It is true, and it is not the same answer: Scheme [13] returns **one** bit for the whole set. The paper must say
so in the figure's own text, next to Fig. 6(c)'s false-rejection measurement, not in a footnote.

## Step 2: redesigned Exp. 3

```
What changes:     one panel instead of three, and the metric becomes the end-to-end cost of an audit (the
                  service's response generation plus the auditor's verification) rather than three separate
                  views of it. No new measurement is needed for the panel itself: both terms are already in
                  metrics.json for every system and every n_Q.
The one graph:    x = returned records n_Q in {10, 10^2, 10^3, 10^4}, log; y = audit cost per query (ms), log
                  = retrieval_ms + verify_ms; five lines: VeRedact-PQ, Shared-Evidence, Per-Record (VeRedact-PQ
                  colour), Scheme [1], Scheme [13].
                  Layout preview from measured 3 Nov data: suggest_change/exp3/exp3_layout_preview.png
Expected figure:  measured today - VeRedact-PQ 97 -> 14,611 ms; Shared-Evidence 20,682; Per-Record 20,543;
                  Scheme [1] 117 -> 37,985 ms; Scheme [13] 70,417 -> 2,848,378 ms.
                  With step 3 (prediction): VeRedact-PQ 14,611 -> ~2,450 ms at n_Q = 10^4, so ~15x below
                  Scheme [1] and ~1,160x below Scheme [13]; the Shared-Evidence and Per-Record lines move with
                  it (they share the same cache-key and PQCH fixes), so SAVER's own margin stays ~1.4x.
Why it's fair:    [x] same hardware for all   - one m7i.4xlarge per run, one untimed history list for every
                      scheme (data/history.py), a fresh auditor per query (Other/docs/experiments.md Exp. 3)
                  [x] baselines per their papers - S1's consistency check is Jia Sec. III-C4; S13's audit is
                      its own challenge/aggregate-proof phase. Neither is reshaped to match ours
                  [x] no point/seed dropped  - all 4 n_Q, all 3 records_per_batch, all 3 runs; the two views
                      dropped from the figure appear in full in the table below
                  [x] the case where we don't win is still shown - the text table carries the two losses
                      (verification 227x and response size 3,163x against Scheme [13]) with their cause, and
                      the caption states that Scheme [13] returns one decision for the whole set
Text changes:     Fig. 5 caption (one panel, end-to-end); the Exp. 3 paragraph citing panels (a)-(c) becomes
                  one paragraph plus the table below; a sentence giving Scheme [13]'s semantics and pointing at
                  Fig. 6(c); Sec. Evaluation gains the sentence that the two costs are paid by different
                  parties and are reported separately in the table.
Cost:             code ~0.5 day for the figure alone (reporting/figures.py:245-...), plus step 3. Rerun Exp. 3
                  only. Measured 3 Nov: 8,651 s per run, of which Scheme [13] alone is 5,170 s and is not
                  touched by any change here - if its finished results are reused (make eval skips a finished
                  (experiment, method, tier)), a run is ~3,480 s: 3 runs ~2.9 h of one m7i.4xlarge
                  (us-east-2, USD 0.806/h) = ~USD 2.3, ~USD 3.5 with the usual 1.5x idle cap. Re-running
                  Scheme [13] as well: ~7.2 h = ~USD 5.8 (~USD 8.7 capped). Needs jaoguya's yes on this issue.
```

### Numbers moved from the graph to the text

| n_Q = 10^4, `records_per_batch` = 64 | VeRedact-PQ | Shared-Evidence | Per-Record | Scheme [1] | Scheme [13] |
|---|---:|---:|---:|---:|---:|
| response generation (ms) | **49.8** | 50.2 | 54.5 | 2,537 | 2,848,314 |
| auditor verification (ms) | 14,561 | 20,632 | 20,488 | 35,448 | **64.2** |
| response size (B) | 67,083,577 | 67,083,577 | 244,513,309 | 4,960,000 | **21,207** |
| decisions returned | 10,000 | 10,000 | 10,000 | 10,000 | **1** |

Plus one sentence: over the evidence-sharing axis (`records_per_batch` ∈ {1, 8, 64}) the authorization nodes
fall 10,000 → 1,251 → 157 and the transition nodes only 10,000 → 9,512 → 7,571 at n_Q = 10^4, so verification
moves just 1.33× (19.3 s → 14.5 s): the axis buys the cheapest node type, and the expensive one (transitions,
at T_CH each) is set by how the history was produced, not by this axis.

## Step 3 — Protocol and implementation changes

**Step 3 needed: yes** — step 2 changes what is plotted, not what is paid. Status: **proposal**, not
implemented, not measured. Every number below is a prediction from the measured breakdown and the Exp. 0 medians.

Where the 15.29 s goes at n_Q = 10^4 (table D1/D2):

| Part | ms | share | crypto model | excess |
|---|---:|---:|---:|---:|
| `state` (PQCH hash per transition) | 11,029 | 72.1 % | z_Q·T_CH = 8,149 | 1.35× |
| `cp` (checkpoint signature per transition) | 2,269 | 14.8 % | c_Q·T_V = 226 | 10.1× |
| `attest` (α_i per record) | 1,111 | 7.3 % | q·T_V = 298 | 3.7× |
| `committee` (t signatures per authorization) | 555 | 3.6 % | a_Q·t·T_V = 23 | 23.7× |
| `rai_mp`, `response` | 78 + 39 | 0.8 % | — | — |

### O1 — verify the PQCH transitions as one batch (implementation only)

`_verify_transition_node` calls `c.ch_verify` once per transition (`veredact.py:677`), 7,571 separate
matrix–vector products. `pqch_sis.py:328` already has **`verify_many`**, which does the whole set as one
matrix–matrix product (`pk.mul_many(R)`) — the verification-side twin of the round-vectorised adaptation
already documented in `Other/docs/experiments.md` §4. Collect every transition's (CH, MR', r') in one pass,
call `verify_many` once, then run the per-record bindings.

- **Predicted: `state` 11,029 ms → ~2,000–2,700 ms** (the 8,149 ms of SIS work becomes one BLAS-level product;
  4× is the conservative end of what numpy gives on 16 vCPU).
- No protocol change, no theorem change, no security change: the same equation is checked for the same inputs.
- Risk to check: `verify_many` returns per-column booleans, so one bad transition must still reject only its
  own records — a test for that goes with the change (`tests/test_fidelity.py`).

### O2 — key the verified-context store on authenticated digests (implementation only)

χ(v) is built per record by hashing the node's whole evidence: χ_auth over the five committee ML-DSA signatures
(16.5 KB), χ_tr over `_raw(CH)` and `_raw(r_new)` (the PQCH arrays), χ_cp over σ_b'. The auditor therefore pays
0.626 ms per record *to decide whether it may skip* 0.18 ms of verification. Key χ instead on values the record
already carries and already checks — (BID) for the authorization node, (b, v_b, v_b′, h_i^PBRP) for the
transition node, (b, v_b′, CP_e^A) for the checkpoint node — and hash the full evidence **once, on insertion**.
Soundness is unchanged: h_i^PBRP already binds Θ_b, Ξ_b, MR_b, MR_b′, v_b, v_b′ and is verified for every record
(`veredact.py:636-644`), and the first verification of the node checked its evidence against the anchored
checkpoint.

- **Predicted: −6.3 s at n_Q = 10^4** (`committee` 555 → 23, `cp` 2,269 → 226, `attest` 1,111 → 298,
  `state` −2,880).
- Manuscript: Sec. SAVER, the definition of χ(v) — the context is the node's identity plus its authenticated
  digest, not a hash of its serialisation. Lemma/Theorem on Reuse(v, χ) keeps its statement.

### O3 — stop shipping σ_b′: anchor the checkpoint digest, not only MR_b′ (protocol)

37.4 % of the response is one ML-DSA signature per transition. The auditor *already* reads the chain for every
transition (`anchored = L.anchor.read("checkpoint_history", …)`, `veredact.py:567`) and compares MR_b′ against
it. Have `anchorCheckpoint` store `H(A_b′)` (32 B) beside MR_b′ in `VeRedactRegistry.sol`; the response then
carries A_b′'s fields (403 B) and the auditor recomputes H(A_b′) and compares with the chain. The chain, not a
signature in the response, is the authority — which is what the manuscript already says about finalization.

- **Predicted: −25.05 MB (−37.4 % of the response) and `cp` 226 ms → ~50 ms** (a hash and a comparison instead
  of an ML-DSA verify).
- Manuscript: Phase 5 Step 6 (what is anchored), Phase 6 Step 5 (checkpoint node), Theorem 5. Security argument:
  the signature was redundant with an on-chain commitment to the same object; the trust root moves from the
  checkpoint authority's key to the PBN, which Theorem 3 already assumes for finalization.
- Contract change, so the image must be rebuilt (`build_image.sh`) before the rerun.

### O4 — BatchAttest: one VPS signature per admission window (protocol)

49.3 % of the response is α_i, one ML-DSA signature per record. The VPS signs one per request
(`veredact.py:181`), plus one receipt rc_i (`veredact.py:191`). Replace both with one signature per admission
window W over a Merkle root of the window's (RID, C_VR) leaves; each request carries root + path
(⌈log₂ W⌉ × 32 B = 256 B at W = 256) and the receipt is the same path.

| | today | with O4 (W = 256) |
|---|---:|---:|
| response bytes per record | 3,309 (α_i) | 256 (path) + 13 (root/window, amortized) |
| Phase 3 signing (Exp. 2) | 2 × T_S = 0.147 ms | 2 × T_S / W ≈ 0.001 ms |
| audit verification per record | T_V = 0.030 ms | ⌈log₂ W⌉ × T_H = 0.010 ms |

- **Predicted: −31.2 MB of response (−46 %), −0.15 ms per request in Exp. 2's Phase 3, `attest` 298 → ~100 ms.**
- Cost: a request is admitted only when its window closes, so Phase 3 gains up to W/λ of latency. Bound it the
  way T_max bounds a round: close the window at W admissions **or** T_vps ms, whichever first.
- Manuscript: Phase 3 Step 5 (α_i becomes (root, path, σ_W)), Phase 4 Step 2 (the committee verifies one σ_W per
  window plus a path per request), Theorem 1 and Lemma 1 (the VPS's statement is now the window root;
  unforgeability of the per-request claim follows from the Merkle binding plus σ_W), Theorem 5 (the receipt).
- This is the same change as Exp. 2 step 3's O3 — propose it once, on whichever issue the reviewer prefers.

### Predicted Exp. 3 after O1–O4 (n_Q = 10^4)

| | measured 3 Nov | predicted | vs Scheme [1] | vs Scheme [13] |
|---|---:|---:|---:|---:|
| response generation (ms) | 49.8 | ~50 | win 51× | win 57,000× |
| auditor verification (ms) | 14,561 | **~2,400** | win 15× | lose 37× |
| response size (B) | 67,083,577 | **~13,400,000** (1,340 B/record) | lose 2.7× | lose 632× |
| end-to-end per query (ms) | 14,611 | **~2,450** | win 15× | win 1,160× |

**We do not catch Scheme [13] on verification or size, and should not claim to.** Its 64 ms and 21 KB buy one
boolean for the whole query; ours buy 10,000 independently verifiable decisions, and Fig. 6(c) measures what
the difference costs it when a record is bad. That sentence belongs in the Exp. 3 text.
