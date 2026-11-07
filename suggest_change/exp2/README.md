# Exp. 2 suggested changes

Issue #6. Three parts: **step 1**, the verdict (why we lose); **step 2**, a redesigned experiment (one panel,
complete authorization cost vs committee size); **step 3**, a protocol change, needed because step 2 alone still
loses below n ≈ 32.

Everything below is read from release `run-2026-11-03` unpacked into `Benchmark/results/`. Reproduce every table:

```bash
python Other/analysis/exp2_step1.py
```

Primitives used as the cost model (Exp. 0 medians, `Overleaf/tables/tab_primitives.tex`):
T_S = 0.0733 ms (ML-DSA-65 sign), T_V = 0.0298 ms (verify), T_ZV = 0.6804 ms (PQZK STARK verify),
T_H = 0.0013 ms (SHA3-256, 64 B).

## Step 1 — Why we lose

### The verdict table

| Point / curve | Win/lose (×) | Cause | Kind | Evidence |
|---|---|---|---|---|
| (a) m = 1 vs Scheme [1] | **lose 3.9×** (2.02 vs 0.52 ms) | at m = 1 nothing amortizes: t = 5 committee signatures (0.64 ms) and the anchoring transaction's build + secp256k1 signing (1.26 ms) are paid by one request | unfair harness (the 1.26 ms is ledger work inside a crypto timer, rule 6) + PQ cost | `exp2_step1.py` table B, column `untimed_remainder`; `anchor.py:206-231` `_sign` runs in the caller's thread inside `p.authorize` (`veredact.py:294`) |
| (a) m = 1 vs Scheme [39] (LETA) | **lose 1.3×** (2.02 vs 1.50 ms) | same fixed cost; LETA's own batch protocol also has a floor at m = 1 (VPD-Tree + Eq. 13) | unfair harness + PQ cost | table A1 |
| (a) m ≥ 8 vs every baseline | **win 1.2–46×** (0.41 → 0.16 ms vs 0.48 / 0.52 / 7.35 ms) | Phase 4 is fixed + 0.152 ms per request; the fixed part (committee + anchoring) divides by m | — | table C: fixed 2.00 ms, marginal 0.1524 ms/request at n = 7 |
| **(a) on the complete cost (Phase 3 + Phase 4/m)** | **lose 3.0× at every m ≥ 8** (1.44 vs 0.48 ms), **6.7× at m = 1** | Fig. 4 plots Phase 4 only. Phase 3 (the VPS: PQZK verify + requester signature + α_i + receipt) is 1.28 ms per request and never amortizes — 89 % of our complete cost at m = 256 | PQ cost (T_ZV = 0.68 ms is 53 % of Phase 3 and 1.4× Scheme [1]'s whole authorization) | table A2; `auth_complete_per_request_ms` in `metrics.json`; `veredact.py:132-196` |
| (a) Scheme [1] flat at ~0.49 ms | lose (see above) | its authorization is t × (hash-to-prime + accumulator membership + 2 ECDSA verifies) per request: no batch protocol exists in the paper, so m requests cost m × the same thing | baseline does less (no PQ, no policy predicate, no freshness, no batch commitment) | `s01_improved_dch/adapter.py:138-158`; `Other/docs/baselines/S1-improved-dch.md` Exp. 2 row; model t·m·2·T_V^c = 17.0 ms vs 34.0 ms measured at m = 64, n = 7 (table D) |
| (a) Scheme [34] flat at ~7.36 ms | **win 46×** at m = 256 | one MA-ABE `Info_Trap` decryption per request: T_Pol = 7.31 ms (Exp. 0), the whole curve | — | `Other/docs/baselines/S34-rebs.md` boundaries; Exp. 0 `T_Pol` |
| (b) Re-ZK vs VeRedact-PQ | **win 14–74×** | Re-ZK re-verifies each PQZK proof in every participating member: the extra is m·t·T_ZV (model 131 → 958 ms, measured extra 154 → 1055 ms over n = 4 → 32) | — | table D, columns `rezk_model` / `rezk_measured_minus_VR` |
| (b) VeRedact-PQ almost flat in n | **win 2.4–122×** | only `committee_ms` depends on n (0.41 → 2.93 ms, model t(T_S+T_V) = 0.31 → 2.27 ms); the m-proportional part (≈ 9.5 ms at m = 64) does not | — | tables B and C |
| **Cost model gap** | — | the four Phase-4 timers explain 24 % of Phase 4 at m = 1 and 95 % at m = 256; the remainder (1.26–2.04 ms, flat in m) is the anchoring transaction. Inside the timers, `attest` costs 4.1× its model (0.127 vs 0.031 ms/request) — one ML-DSA verify plus four SHA3 calls, **one of them over the whole STARK proof** (`c.H(ev["proof"])`) | unfair harness (rule 6) + implementation | table B; `veredact.py:231-241` |

Kinds used: *baseline does less · PQ cost · unfair harness · workload doesn't use our mechanism.*

### The three answers the table rests on

1. **We start beating Schemes [1] and [39] at m = 8** on the plotted metric (0.406 vs 0.497 / 0.618 ms), and
   never on the complete metric. Per-request split at n = 7 (table B, divided by m): attest 0.127 ms,
   fresh 0.009 ms, commit 0.013 ms; committee 0.68 ms *per set*, not per request.
2. **The measured per-set cost does not match the model** m(T_V + 2T_H) + m·T_H + 2m·T_H + t(T_S + T_V).
   At m = 64, n = 7 the model gives 2.85 ms and the measurement 11.54 ms. The 8.69 ms gap splits into:
   the per-request `attest` step at 3.9× its crypto cost (5.93 ms), the anchoring transaction (1.40 ms),
   `commit` and `fresh` above their hash models (0.69 + 0.50 ms), and the committee loop at 1.3× (0.16 ms).
3. **m = 1 and m = 256 are not operating points.** CORA produced rounds of 53–161 requests (median) at every
   rate in Exp. 1 (table E). The deployed system lives in the middle of the axis, where the plotted metric wins
   and the complete metric loses 3×.

### What a reviewer will say

Fig. 4 compares our Phase 4 against the baselines' *whole* authorization. Scheme [1] has no Phase 3 to leave
out. Stated as the complete cost the figure reverses: we are 3.0× slower than Scheme [1] and 2.8× slower than
Scheme [39] at every batch size. Step 2 plots the complete cost.

## Step 2: redesigned Exp. 2

```
What changes:     metric (the complete authorization cost that metrics.json already records), axis (committee
                  size n becomes the one axis, extended to 48 and 64), and one measurement fix (rule 6).
The one graph:    x = committee size n in {4, 7, 10, 16, 32, 48, 64}, log; y = authorization per request (ms),
                  log = Phase 3 + Phase 4/m at the reference round m = 64; five lines: VeRedact-PQ, Re-ZK,
                  Scheme [1] and Scheme [34] (dashed, "no batching"), Scheme [39].
                  Layout preview from measured 3 Nov data: suggest_change/exp2/exp2_layout_preview.png
Expected figure:  VeRedact-PQ nearly flat: 1.34 ms (n=4) -> 1.40 ms (n=32) -> ~1.43 ms (n=64), i.e. today's
                  1.45-1.51 ms minus the anchoring (1.3 ms / 64 = 0.02) and minus fix 4 (0.09); predictions
                  beyond n=32 extrapolate the measured linear-in-t committee term.
                  Scheme [1] rises as t(n): 0.42 (n=4) -> 1.46 (n=32) measured -> ~2.6 ms (n=64), crossing
                  VeRedact-PQ at n ~ 30; Scheme [34] 5.0 -> 27.4 -> ~52 ms; Re-ZK 3.9 -> 17.0 -> ~32 ms;
                  Scheme [39] flat at 0.51 ms (no committee, so no n dependence).
Why it's fair:    [x] same hardware for all   - one m7i.4xlarge per run, every system (README Hardware)
                  [x] baselines per their papers - [1] and [34] define no batch protocol, so a set of m is m
                      authorizations and their lines stay dashed (S1-improved-dch.md, S34-rebs.md); [39] keeps
                      its own batch protocol; committee members are timed serially for every threshold scheme
                  [x] no point/seed dropped  - the m axis keeps all six sizes, it moves to a table
                  [x] the case where we don't win is still shown - Scheme [39] is below us at every n and
                      Scheme [1] below us until n ~ 32, both inside the panel
Text changes:     Fig. 4 caption (one panel, complete cost); the Exp. 2 paragraph that cites panels (a)/(b)
                  becomes one paragraph on the n axis plus the amortization table below; Table I note that
                  Scheme [39] authenticates faster because it has no committee, no policy predicate and no
                  freshness check; the measurement-limits list gains "anchoring is ledger time, reported
                  separately" (rule 6).
Cost:             code ~1 day (4 small changes, below); rerun Exp. 2 only, 3 runs. Measured 3 Nov: 3,670 s per
                  run; two extra committee sizes -> ~1.4x -> ~4.3 h of one m7i.4xlarge (us-east-2, USD 0.806/h)
                  = ~USD 3.5, ~USD 5.2 with the usual 1.5x idle cap. Needs jaoguya's yes on this issue.
                  Risk: the SIS-PQCH DKG is untimed setup but ~5 min at n = 32 and superlinear; n = 64 may add
                  20-30 min per run. It is cached per (seed, n, t) in .cache/pqch_dkg/, so it is paid once.
```

### The four code changes

| # | Where | Change | Effect |
|---|---|---|---|
| 1 | `reporting/figures.py:205-240` | one panel; plot `auth_complete_per_request_ms` at m = `reference_batch`; the m axis becomes a table | the loss becomes visible |
| 2 | `configs/experiments/exp02_authorization_latency.yaml` | `committee_sizes: [4, 7, 10, 16, 32, 48, 64]` | shows the crossing with Scheme [1] |
| 3 | `veredact.py:290-300` | move `L.anchor.submit("abrrr_authorization", …)` out of `authorize()`: return the Future to `VeRedactScheme.authorize_batch`, which records it as ledger time | removes 1.26–2.04 ms of secp256k1 + ABI work from a crypto timer (rule 6). Helps us; do it anyway |
| 4 | `veredact.py:231-241` | drop `c.H(ev["proof"])` from the Phase 4 attestation check (see step 3, O2) | −0.09 ms per request |
| 5 | `s34_rebs/adapter.py`, `s99_leta/adapter.py` | fill in `auth_cost()` (both report all-zero counters today) | rule 7: capabilities and costs beside every number |

### Numbers moved from the graph to the text

| m (round size) | VeRedact-PQ complete (ms) | Scheme [1] | Scheme [39] | Scheme [34] |
|---:|---:|---:|---:|---:|
| 1 | 3.45 | 0.52 | 1.56 | 7.40 |
| 8 | 1.73 | 0.50 | 0.68 | 7.39 |
| 64 | 1.46 | 0.48 | 0.58 | 7.36 |
| 256 | 1.44 | 0.49 | 0.58 | 7.35 |

at n = 7. One sentence with it: CORA produced rounds of 53–161 requests in Exp. 1, so the deployed system sits
between the m = 32 and m = 256 rows.

## Step 3 — Protocol optimisation

**Step 3 needed: yes** — after step 2 we still lose to Scheme [1] below n ≈ 32 and to Scheme [39] at every n.
Status: **proposal**, not implemented, not measured. Every number below is a prediction from the Exp. 0 medians.

Where the 1.44 ms goes (table A2 and B, at n = 7, m = 64):

| Part | ms | What it is |
|---|---:|---|
| Phase 3, PQZK verify | 0.680 | `c.zk_verify` — the private-policy predicate |
| Phase 3, 2 ML-DSA signs | 0.147 | α_i (the VPS attestation) and rc_i (the requester's receipt) |
| Phase 3, 1 ML-DSA verify | 0.030 | σ_R, the requester's signature |
| Phase 3, hashes + Python | 0.426 | SA-RLI lookup, membership hashes, state digest, interpreter |
| Phase 4 / m, attest | 0.127 | 1 ML-DSA verify + 4 SHA3 calls, one over the whole STARK proof |
| Phase 4 / m, rest | 0.022 + 0.018 | freshness, batch commitment, committee / m |

### O2 — drop the proof re-hash in Phase 4 (no security cost)

`veredact.py:235` recomputes `h_proof = c.H(ev["proof"])` over the full STARK proof once per request, to check
that the stored evidence reconstructs C_VR. But C_VR is already bound to h_i^PQ inside α_i, which the same block
verifies one line earlier, and Phase 6 re-derives h_proof from the evidence on every escalated record
(`verify_audit`, `rr.RID in deep`). The re-hash therefore detects only a corrupted evidence store between
Phases 3 and 6 — which the audit detects anyway. **Predicted saving 0.09 ms per request (6 %).** No theorem
changes: Theorem 1's binding is through α_i, not through this hash.

### O3 — one receipt signature per round (no security cost)

`veredact.py:191-193` signs rc_i with ML-DSA per request so the requester holds a signed admission receipt.
Replace it with one signature over a Merkle root of the round's receipts; the requester gets (root, path, ts).
**Predicted saving 0.072 ms per request (5 %).** Theorem 5 gains a Merkle path in the receipt's definition; the
signed statement is unchanged.

### O4 — split the PQZK proof: a credential token + a per-request binding

**The one change that decides Exp. 2.** Today every request carries a STARK over
`ValidCred ∧ RequesterBound ∧ PrivatePolicy`, verified per request at 0.680 ms. Of those three predicates only
`RequesterBound`'s binding to x_i changes between two requests by the same requester under the same policy in
the same epoch: `ValidCred` (membership + expiry) and `PrivatePolicy` (attribute ≥ threshold bound in C_P) are
properties of (requester, policy, epoch).

```
Setup   (unchanged) credential registry, C_P binds its root.
Token   the requester proves ValidCred ∧ PrivatePolicy ∧ "the credential's leaf commits to vk_r" ONCE per
        (requester, policy, token epoch Δ), to the VPS. The VPS caches TOK = (vk_r, PID, C_P version,
        expiry = now + Δ) and signs it; the cache key is H(vk_r ‖ PID ‖ C_P ‖ epoch).
Request the requester signs x_i under vk_r (ML-DSA). Phase 3 verifies: TOK unexpired, TOK's C_P version is
        current, and the signature over x_i under TOK.vk_r.          -> T_V instead of T_ZV
```

| | per request today | with O4 |
|---|---|---|
| PQZK verify | 0.680 ms | 0 (amortized: one 0.680 ms verify per Δ per requester–policy pair) |
| extra ML-DSA verify over x_i | — | 0.030 ms |

**Predicted complete cost with O2 + O3 + O4: 1.44 − 0.680 + 0.030 − 0.072 − 0.090 = 0.63 ms**, i.e. below
Scheme [1] from n = 7 upwards and within 1.2× of Scheme [39] — with the committee, the policy predicate and the
freshness check that neither of them has.

#### What it costs in security (state this in the paper, do not hide it)

| Property | Today | With O4 |
|---|---|---|
| Unlinkability | each proof is independent: two requests by one requester are unlinkable | requests sharing a token are **linkable to each other** (same vk_r) for at most Δ. Not linkable to the real identity: vk_r is a fresh per-token key committed inside the proof |
| Revocation latency | takes effect at the next request (the proof is against the current registry root) | takes effect at **token expiry**, ≤ Δ. Mitigation: the VPS drops every token whose C_P version is stale, so a *policy* change is immediate; only a *credential* revocation waits |
| Attribute privacy | attribute never disclosed | unchanged — the token proves `attribute ≥ threshold`, never the value |
| Binding to x_i | inside the STARK (Fiat–Shamir over the statement digest) | an ML-DSA signature over x_i under a key the STARK committed to |

Δ is a config value (`veredact.token_window_s`), the same kind of knob as the epoch e. Δ = 0 is today's protocol.

#### Manuscript changes O4 would need

| Section | Change |
|---|---|
| Notation table | TOK, vk_r, Δ |
| Phase 1 Step 6 | the credential leaf commits to vk_r |
| Phase 2 | token issuance: the requester's one-off proof and the VPS's signed TOK |
| Phase 3 Step 4 | replace "verify π_i^PQ" by "verify TOK and Sign_{vk_r}(x_i)"; escalation still verifies the token's proof |
| Theorem 1 (binding) | the binding to x_i is the ML-DSA signature; the proof's Fiat–Shamir clause moves to the token |
| Theorem 2 / privacy | add the linkability clause (within Δ) and the revocation bound (≤ Δ) |
| Phase 6 | an escalated audit verifies the token's STARK, not a per-request one: `nodes_zk` becomes per (requester, policy, Δ) |

#### If the team rejects O4

Then Exp. 2 is reported as a loss and the paper says so in one sentence: *"VeRedact-PQ authorizes a request in
1.35 ms against 0.48 ms for Scheme [1] and 0.58 ms for Scheme [39] at n = 7; the 0.68 ms difference is the per-request
PQZK verification that enforces the private policy, which neither scheme performs (Table I)."* The committee
axis still wins from n ≈ 32, and that is a defensible claim on its own.
