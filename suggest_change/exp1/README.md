# Exp. 1 suggested change: leaf-level freshness (`FreshLeaf`)

Issue #5 (step 3 candidate). Manuscript copy with every change in `\textcolor{red}{…}`:
[`VeRedact-optimize2.tex`](VeRedact-optimize2.tex) (the original `Overleaf/VeRedact-optimize.tex` is unchanged).
Status: **proposal**, not implemented, not measured. All effects below are predictions.

## Problem (measured, release `run-2026-11-03`)

Above ~500 req/s VeRedact-PQ's throughput falls (247/s at 250 req/s → ~110/s at 2,000–5,000 req/s) while
Scheme [27] holds ~140/s. Cause: **stale-proof churn** (`Other/analysis/exp1_step1.py`, tables A–C).

- A request's proof binds `h_st`, which contains the **whole state of its batch** (`State_b`: MR_b, v_b, …).
- A redaction of *any* leaf of batch b changes `State_b`, so every pending proof on batch b becomes stale,
  even when its own leaf is untouched.
- Zipf-hot batches change in almost every round; proofs wait 3–5 s in the VPS queue; they arrive stale,
  are re-proved, and the re-proofs lengthen the queue: 93–95 % of ~2,000 validations/s are wasted at
  ≥ 1,000 req/s, and rounds shrink to 65–78 requests (B_max 256).

## Batch vs round

| Term | Meaning |
|---|---|
| **Batch b** | fixed group of 256 committed transactions; root MR_b, chameleon hash CH_b, version v_b (391 batches) |
| **Round** | one CORA selection → one committee authorization → one SFMR execution (~2 per second) |
| **Version v_b** | +1 per round that redacts something in batch b (one SFMR update + one PQCH adaptation) |

## The change

Split `h_st` into what the request is about and which snapshot it was validated against:

```
h_leaf = H(TID_i ‖ I_i ‖ D_i ‖ pos_i)
h_snap = H(enc(State_b))
h_st   = H(h_leaf ‖ h_snap)          (still the single value inside x_i and C_i^VR)
```

Replace "h_st equals the current state" by one predicate, used in Phase 3 (VPS), Phase 4 (committee) and
Phase 5 (execution):

```
FreshLeaf_i = 1  iff  (1) H(h_leaf ‖ h_snap) = h_st
                      (2) h_leaf = H(TID_i ‖ I_i ‖ D_i^cur ‖ pos_i)          own leaf unchanged
                      (3) h_snap = H(enc(State_b^(v))) for an ANCHORED checkpoint, v_cur − k ≤ v ≤ v_cur
                      (+ epoch and policy-version checks, unchanged)
```

### Example (batch 17)

```
t=0.0  A → batch 17 leaf 5, B → batch 17 leaf 9; both proved against batch 17 version 3
t=0.4  B executed (round #1): batch 17 v3 → v4; leaf 5 unchanged
t=4.0  A reaches the VPS; batch 17 is at v8
       today:     h_st(v3) ≠ h_st(v8)                                 → stale → re-prove
       FreshLeaf: (2) leaf 5 still D_5 ✓  (3) v3 anchored, within k ✓  → accepted, no re-proof
       executed on batch 17's LATEST root (v8 → v9)
If B had changed leaf 5 itself: (2) fails → A rejected (correct).
```

## Rules that come with it

1. **Execution uses the latest state.** Phase 5 always starts from the current MR_b, r_b, v_b (the code already
   does: `veredact.py:355-372`); the snapshot only certifies that validation used an authentic, recent checkpoint.
2. **k** (snapshot window) bounds how old a validation may be. Open decision: about the number of rounds in a
   few seconds.
3. **Same leaf, same round**: one change per transaction per round (unchanged, `veredact.py:327-333`).
4. **Same leaf, later round**: (2) fails → rejected (correct conflict).
5. **ABA** (leaf changes and changes back): impossible except by collision, since D = H(m ‖ ρ) with fresh ρ.
6. **Evidence and audit**: PBRP_i records `v_snap` next to v_b → v_b′; the auditor checks h_snap is anchored
   within k of v_b and the executed old leaf L_i = H(I_i ‖ D_i) matches h_leaf (leaf unchanged from validation
   to execution).

Unchanged: RADC, SFMR, PQCH (one adaptation per batch per round), C_i^VR, α_i, SAVER's κ(v).

## Manuscript changes (red in `VeRedact-optimize2.tex`)

| Section | Change |
|---|---|
| Notation table | h_leaf, h_snap, k, FreshLeaf |
| Phase 3 Step 4 | h_st = H(h_leaf ‖ h_snap); FreshLeaf definition (Eq. `freshleaf`); why neighbour redactions no longer invalidate |
| Phase 4 Step 2 | committee re-check uses FreshLeaf instead of ĥ_st = h_st |
| Phase 5 Step 1 | execution re-check uses FreshLeaf; execution starts from the latest finalized state |
| Phase 5 Step 6 | PBRP_i gains v_snap |
| Phase 6 Step 4 | request check: snapshot anchored within k, leaf unchanged |
| Theorem 1 | h_st definition (eq. `sec_state_digest`) |
| Lemma 1 | revalidation uses FreshLeaf |
| Theorem 4 | statement and proof rewritten for leaf freshness + anchored, recent snapshot (removed sentence: "a request validated against an earlier state produces a different state digest after the relevant state changes") |
| Theorem 5 | PBRP_i gains v_snap |

Not yet written: Exp. 1 text and figure (after the rerun), and any Exp. 3/4 effect on the audit cost (one extra
anchored-checkpoint lookup per request node, likely shared per (b, v_snap)).

## Code changes (to implement after approval)

| Where | Change |
|---|---|
| `veredact.py:116-120` `state_digest` | return (h_leaf, h_snap) and h_st |
| `veredact.py:157` (Phase 3) | `FreshLeaf` instead of `R.h_st != h_st` |
| `veredact.py:254` (Phase 4) | `FreshLeaf` instead of `state_digest(...) == vr.h_st` |
| `veredact.py:329` (Phase 5) | `FreshLeaf` instead of `bt.v != vr.v_b` |
| PBRP / audit (`verify_audit`) | record and check `v_snap` |
| config | `veredact.snapshot_window_k` |
| tests | neighbour redaction accepted; same leaf rejected; snapshot older than k rejected; forged snapshot rejected; ABA |

## Expected effect (prediction, to be measured by a rerun)

- Stale rejections only when the request's own leaf changed: ~1/256 of today's same-batch rate.
- No re-proof feedback loop, so the curve rises past 250 req/s and flattens at a higher ceiling (bound by
  B_max/T_max, the VPS or the executor) instead of falling; that ceiling stays visible in the figure.
- Same-batch requests stay valid in the queue longer, so CORA can group them: more SFMR sharing per adaptation.
