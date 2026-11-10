# Implementation plan — applying the Exp. 1–5 redesigns

Issue #13. This is the single list #13 step 1 asks for: every change proposed on #5–#9, deduplicated, ordered,
with the overlaps resolved. Read this first if you are picking the work up; each lane's reasoning stays in its
own `suggest_change/exp<N>/README.md`, and the evidence behind it in `Other/analysis/exp<N>_step1.py`.

Written 8 Nov 2026 against `main` = `2e2283e` (tag `run-2026-11-03` + 3 commits, none of which touch
`Benchmark/`). Numbers quoted here come from release `run-2026-11-03`.

## 0. Status gate — read before writing code

| Issue | Lane | Owner | Reviewer | Step 1 | Step 2 | Step 3 |
|---|---|---|---|---|---|---|
| #5 | Exp. 1 throughput | Ppdfd | yewza101 | posted, quiz 3/6 passed, **awaiting ✅** | posted | posted (FreshLeaf) |
| #6 | Exp. 2 authorization | Ppdfd | yewza101 | posted | posted | posted |
| #7 | Exp. 3 audit | yewza101 | Ppdfd | posted | posted | posted |
| #8 | Exp. 4 verification | yewza101 | Ppdfd | posted, quiz overridden | posted | — |
| #9 | Exp. 5 blockchain | Ppdfd | yewza101 | posted | posted | posted |

**No step has been accepted by a reviewer yet** and #13 is blocked by all five. Everything in §1 below is safe
to land anyway — it fixes measurement bugs, uses code that already exists, or removes a rule violation, and
none of it changes the protocol or the manuscript. Everything in §2 and §3 waits for the ✅ on its lane.

Unpack the release into `Benchmark/results/` before running any analysis script:

```bash
gh release download run-2026-11-03 --repo Jaoguya/VeRedact --dir /tmp/rel
cd /tmp/rel && for f in experiment-reps per-run rows; do unzip -oq $f.zip -d .; done
cp -r /tmp/rel/exp0*/. /tmp/rel/exp*/. "$REPO/Benchmark/results/"   # gitignored
```

## 1. Safe now — measurement and implementation fixes

No protocol change, no manuscript change, no reviewer gate. Each is one PR.

| # | Change | Files | Why it is safe | Effect |
|---|---|---|---|---|
| **S1** | Move `anchor.submit("abrrr_authorization", …)` out of the Phase 4 crypto timer; return the Future to `VeRedactScheme.authorize_batch` and record it as ledger time | `methods/veredact/protocol/veredact.py` (`authorize`), `veredact_scheme.py` (`authorize_batch`) | rule 6 says crypto and ledger time are never summed; today `_sign` runs in the caller's thread inside the timer | Exp. 2: −1.26 to −2.04 ms per authorized set (58 % of the m = 1 point). Helps us; it is still a bug |
| **S2** | Drop `h_proof = c.H(ev["proof"])` from the Phase 4 attestation check | `veredact.py` (Phase 4 `authorize`) | C_VR already binds h_i^PQ inside α_i, verified one line earlier; Phase 6 re-derives it on every escalated record | Exp. 2: −0.09 ms per request |
| **S3a** | Key the **authorization** node's χ(v) on `(BID)` instead of a hash of C_B, R_VR and the t committee signatures | `veredact.py` (`verify_audit`, `chi_auth`) | `auth` is read from the verifier's own store by BID, so BID alone determines the evidence `_verify_auth_node` recomputes. Nothing from the response enters the key | Exp. 3/4: `committee` 555 → ~23 ms |
| **S4** | Use the existing `PQCHSis.verify_many` for the round's transitions instead of `ch_verify` per transition | `veredact.py` (`_verify_transition_node` → collect-then-verify) | `verify_many` is already in `crypto/pqch_sis.py` and is the verification twin of the round-vectorised adaptation already documented in `experiments.md` §4 | Exp. 3/4: `state` 11.0 s → ~2.0–2.7 s (the 4× is an estimate — see §5) |
| ~~S5~~ | ~~Fill in `auth_cost()` in the S34 and S99 adapters~~ | — | **withdrawn, see below** | — |
| **S7** | Sign `H(r_b′)` in A_b′ instead of `r_b′` itself, hashed once when the checkpoint is built | `protocol/types.py`, `ledger.py` (`_checkpoint`), `veredact.py` (`_verify_checkpoint_node`) | the signature binds the same value through one more hash; the PQCH equation is what binds r_b′ to CH_b and MR_b′, exactly as before. The contract's `Checkpoint` struct already declares `rDigest`, so this aligns the Python side with it | Exp. 3/4: `cp` 2,269 → ~300 ms (r_b′ is 2nk int64 = 64 KiB, re-hashed per checkpoint node today) |
| **S6** | Record `gas_used` for both Exp. 5 transactions | `evaluation/experiments/exp05_blockchain_overhead.py`, `evaluation/summaries.py` | every Future already resolves to `(ledger_ms, gas_used)`; Exp. 5 threw the gas away with `_` | decides whether the chain is transaction- or byte/gas-bound, which Exp. 5's whole comparison turns on |

**S5 withdrawn (correction to #6's step 1).** The verdict table on #6 says S34 and S99 "report all-zero
`auth_cost()`, so rule 7 is only half met". Reading the adapters, the zeros are **deliberate and already
documented in the code**: S34's authorization is an MA-ABE decryption (2t pairings + t GT exponentiations,
`s34_rebs/adapter.py` `auth_cost`) and S99's per-request step is one `h0` hash check
(`s99_leta/adapter.py:86-93`), with its only verification being one *aggregate* check per batch. Neither is a
signature verification, a proof verification or a signature generation, which are the only things `AuthCost`
names. So the adapters are right and the **metric's vocabulary** is what is incomplete — `AuthCost` has no
field for pairings or for batch-level verifications. Extending it changes a column in every system's rows, so
it is a deliberate choice for the team, not a free fix. Posted as a correction on #6.

**Test for each:** S1 — a Phase 4 timing test that asserts no ledger call inside the timer. S2/S3a — existing
fidelity tests must still reject what they rejected (a tampered evidence blob, a stale checkpoint). S4 — one
bad transition rejects only its own records (`verify_many` returns per-column booleans). S6 — a smoke row has
non-empty `finalize_gas`.

## 2. Protocol changes — one ✅ each before coding

Each needs a red-marked manuscript copy in `suggest_change/<lane>/VeRedact-optimize2.tex` (see §4).

| # | Change | Lane | Touches | Predicted effect |
|---|---|---|---|---|
| **P1** ✔ | **FreshLeaf** — `h_st = H(h_leaf ‖ h_snap)`; a request stays fresh while its own leaf is unchanged and its snapshot is an anchored checkpoint within k versions | #5 | Phases 3/4/5, PBRP gains `v_snap`, Phase 6 request check, config `snapshot_window_k` = 8 | **implemented**; Exp. 1: throughput should stop collapsing above 250 req/s |
| **P2** | **BatchAttest** — the VPS signs one Merkle root per admission window W instead of α_i and rc_i per request | #6 O3 ≡ #7 O4 | Phase 3 Step 5, Phase 4 Step 2, Theorem 1, Lemma 1, Theorem 5 | Exp. 2: −0.15 ms per request · Exp. 3: −30.4 MB of response |
| **P3** | **Anchor `H(A_b′)`** so the audit response need not carry σ_b′ | #7 O3 | `_checkpoint`, `verify_audit`, `VeRedactRegistry.sol` `anchorCheckpoint` | Exp. 3: −25.1 MB, `cp` 226 → ~50 ms |
| **P4** | **RoundCheckpoint** — one σ_e over a Merkle root of the round's checkpoints plus an inclusion path per batch, instead of σ_b′ per batch | #9 | Phase 5 Steps 5–6, Phase 6 Step 5, Theorems 3 and 5, same contract call | Exp. 5: transaction 6.2× smaller, 304 B per redaction |
| **P5** | **Credential token** — `ValidCred ∧ PrivatePolicy` proved once per (requester, policy, Δ); each request carries an ML-DSA signature over x_i under the token's key | #6 O4 | Phase 1 Step 6, new Phase 2 issuance, Phase 3 Step 4, Theorems 1–2, Phase 6 escalation | Exp. 2: 1.27 → 0.63 ms. **Costs linkability within Δ and revocation latency ≤ Δ** |
| **P6** | **Paper-conformance gap #1** — check PQCH for the old *and* the new state (2·T_CH per transition), as the manuscript specifies | #8 | `_verify_transition_node` | **Adds ~8.1 s** at n_Q = 10^4. See the warning in §3 |
| ~~P7~~ | ~~Store `r_b′` as int32~~ → **done as S7** (sign `H(r_b′)`), see §1 | #8 | — | — |
| **S3b** | Key the **transition** and **checkpoint** nodes' χ(v) cheaply too | #7 O2, #8 | audit response format, `verify_audit` | Exp. 3/4: a further −5.8 s at n_Q = 10^4 |

**Why S3b is not in §1.** The transition and checkpoint evidence arrives *inside the response*, one copy per
record, so the only thing that safely identifies a node is a digest of that evidence — which is the expensive
hash we want to remove. `h_i^PBRP` does not help: it binds Θ_b, Ξ_b, MR_b, MR_b′, v_b and v_b′ but **not r_b′**,
so two records with equal h_i^PBRP and different r_b′ would share one verdict and a forged r_b′ would be
accepted. The fix is the one the manuscript already describes and #8 named: the response references shared DAG
nodes **by id** and carries each node once, after which χ(v) is the node id. That is a response-format change,
so it rides with P3.

## 3. Overlaps and ordering — the part that bites

**P3 and P4 are the same code path.** Both rewrite what `_checkpoint` / `execute` put in the checkpoint and
what the contract stores. Land them as **one** PR with **one** image rebuild, not two.

**P2 serves two lanes.** #6 asked for it to cut Phase 3 signing, #7 asked for it to cut the response. Same
change — implement once, reference both issues.

**S3a/S3b serve two lanes.** The per-record χ hashing was found independently on #7 and #8.

**P1 reaches into #7 and #8.** FreshLeaf adds `v_snap` to PBRP and a snapshot check to Phase 6, both inside
what Exp. 3 and Exp. 4 measure. Anyone touching `verify_audit` must rebase onto it.

**⚠️ P6 works against S4 and S3a/S3b.** Fixing the conformance gap *doubles* the PQCH work the auditor does, adding
~8.1 s at n_Q = 10^4 — more than S3a, S3b and S4 save together unless the batching lands first. Sequence: **S4 → S3a → S3b
→ P6**, and report the three as one line in the paper, never P6 alone. Landing P6 first would make Exp. 3 and
Exp. 4 look like a regression against the 3 Nov release.

**S7 lands before P3/P4.** The checkpoint signature's message changes shape, and P3 anchors `H(A_b′)` over
that same message, so S7 goes first (it already has).

**Rounds couple all five experiments.** P1 makes rounds larger, which raises records-per-transition (today
1.32). That lowers Exp. 3's z_Q and Exp. 5's affected batches per redaction. So the Exp. 3 and Exp. 5
predictions are **lower bounds** if P1 lands, and Exp. 3's sharing claim stays weak if it does not.

### Order to implement

```
1. S1  S2  S6  S7          independent, any order, no rebases
2. S4                      batched PQCH verify      (must precede P6)
3. S3a                     authorization chi key
5. P1  DONE                FreshLeaf                (everything below rebases onto it)
6. P2                      BatchAttest              (#6 + #7)
7. P3 + P4 + S3b together  H(A_b'), RoundCheckpoint and nodes-by-id: one contract change, one rebuild
8. P6                      conformance gap, reported together with S3a, S3b and S4
9. P5                      credential token         (only if the team accepts the privacy trade)
10. Experiment redesigns   §4 below
11. Manuscript merge       one PR
12. Rerun                  AWS, one yes per action (owner in chat or team member on the issue)
```

## 4. Experiment redesigns (after the ✅ on each lane's step 2)

| Exp. | One panel | Config / code |
|---|---|---|
| 1 | finalized **valid** redactions/s vs offered load, 25–1,000 req/s | `fault_fraction` 0.20, new `fault_kinds: [stale, absent]` in `data/dataset.py`; metrics `valid_throughput_per_s`, `invalid_accepted` in `evaluation/summaries.py`; variants move to a table |
| 2 | complete authorization per request vs committee size n ∈ {4,7,10,16,32,48,64} at m = 64 | plot `auth_with_net_per_request_ms` (crypto + committee network time, fairness fix option 1, 2026-11-08; crypto alone `auth_complete_per_request_ms` for the text); `systems:` drops `veredact-re-zk`; `Other/docs/experiments.md` §2–3 drop it too |
| 3 | end-to-end audit cost (generation + verification) vs n_Q | `reporting/figures.py` `fig_exp3`; the other two views become a text table |
| 4 | auditor verification vs n_Q with S13-per-block at equal granularity | already coded on `8-exp4-analysis` (adapter, registry, config, figure, 3 tests) |
| 5 | PBN anchoring transactions per finalized redaction vs offered load | `systems:` gains the four baselines; a rate loop; `affected_batches` → {1, 8, 32, 64, 128}; new row columns (see S6) |

## 5. Manuscript

**Do not edit `Overleaf/VeRedact-optimize.tex` yet.** Agreed on #5: each lane keeps a full copy at
`suggest_change/exp<N>/VeRedact-optimize2.tex` with every change wrapped in `\textcolor{red}{…}`, and they are
merged into `Overleaf/` **once, in one PR, at the end** (#13 step 4). Only `exp1` has such a copy today.

Sections each change touches:

| Change | Manuscript |
|---|---|
| P1 FreshLeaf | notation table; Phase 3 Step 4; Phase 4 Step 2; Phase 5 Steps 1 and 6; Phase 6 Step 4; Theorem 1; Lemma 1; Theorem 4 (rewritten); Theorem 5 |
| P2 BatchAttest | Phase 3 Step 5; Phase 4 Step 2; Theorem 1; Lemma 1; Theorem 5 |
| P3 H(A_b′) | Phase 5 Step 6; Phase 6 Step 5; Theorem 5 |
| P4 RoundCheckpoint | Phase 5 Steps 5–6; Phase 6 Step 5; Theorem 3; Theorem 5 |
| P5 credential token | notation table; Phase 1 Step 6; new Phase 2 issuance; Phase 3 Step 4; Theorems 1 and 2; Phase 6 escalation |
| P6 conformance gap | the Phase 6 transition check already says 2·T_CH — the **code** changes, not the text |
| Exp. 1–5 redesigns | each experiment's paragraph and figure caption; Table I note on Scheme [39]; the measurement-limits list gains "anchoring is ledger time, reported separately" |

## 6. Freeze the predictions before rerunning

#13 step 2. The numbers are already written down per lane; collect them here before any AWS action, and after
the rerun investigate every difference rather than tuning it away.

| Exp. | Metric | 3 Nov | predicted after |
|---|---|---:|---:|
| 2 | complete authorization per request (crypto), n = 7, m = 64 | 1.457 ms | 1.27 ms (S1+S2+P2), **0.63 ms** with P5; the committee term drops to the slowest member + serial approval checks (fairness fix) |
| 2 | Fig. 4 line: crypto + committee network time, n = 7, m = 64 | — (not recorded) | VeRedact-PQ ≈ crypto + 10/64 ≈ 0.16 ms; Scheme [1] ≈ its crypto + 10 ms: **below Scheme [1] at every n by ≈ the 10 ms delay** (set by `message_delay_ms`; we win only while one round costs more than our crypto gap, ≈ 0.9 ms on 3 Nov) |
| 2 | committee size where Scheme [1] crosses us, crypto alone | n ≈ 30 | **superseded** (fairness fix): Scheme [1]'s t node checks now cost one member, so its crypto no longer grows with t; likely no crossing on crypto alone (text table) |
| 3 | auditor verification, n_Q = 10^4 | 14,561 ms | ~2,350 ms (S3+S4+P2+P3), **+8,100 ms if P6 lands** |
| 3 | response size, n_Q = 10^4 | 67.1 MB | ~11.6 MB |
| 5 | finalization transaction at \|Ω_e\| = 32 | 119,120 B | **19,086 B** |
| 5 | on-chain bytes per redaction | 1,860 B | **304 B** |
| 1 | VeRedact-PQ throughput above 250 req/s | falls to ~110/s | rises then plateaus (P1) |
| 1 | Scheme [27] / [1] valid throughput at saturation | ~137–148 /s / ~60 /s | [27] ≈ 126/s (chain-bound, executes stale); [1] ≈ 54/s per #5, **may rise** now that its node checks run in parallel and its committee rounds are pipelined (`baseline_inflight`) |

Confidence: highest for the Exp. 5 figures (the ABI model already reproduces every measured point exactly);
lowest for S4's 4× batching factor, which alone moves Exp. 3's total between ~1.9 s and ~5 s.

**Cheapest way to remove that uncertainty before spending any AWS budget:** time `verify_many` against a loop
of `ch_verify` over 7,571 transitions in one smoke run on the server. One script, a few minutes, and it decides
whether Exp. 3's headline is ~2 s or ~5 s.

## 7. AWS

Per-experiment rerun estimates from the 3 Nov logs (m7i.4xlarge, us-east-2, USD 0.806/h; ×1.5 idle cap):

| Rerun | Per run | 3 runs | Cost |
|---|---:|---:|---:|
| Exp. 2 (Re-ZK dropped, two extra committee sizes) | ~1.05 h | ~3.1 h | ~USD 2.5 (3.8 capped) |
| Exp. 3 (Scheme [13] results reused) | ~0.97 h | ~2.9 h | ~USD 2.3 (3.5 capped) |
| Exp. 3 (Scheme [13] re-run too) | ~2.4 h | ~7.2 h | ~USD 5.8 (8.7 capped) |
| Exp. 5 (baselines added) | ~0.4 h | ~1.2 h | ~USD 1.0 (1.5 capped) |

Exp. 1 and Exp. 4 estimates belong to #5 and #8. Every AWS action needs one yes naming that action, from the
agent's owner in chat or a team member
as a comment on its issue (`CLAUDE.md` § Guardrails). A contract change (P3/P4) means `build_image.sh` first.

## 8. Verifying the work

```bash
cd Benchmark && make test lint          # on the server, via deploy/aws/remote.sh
python Other/analysis/exp2_step1.py     # tables behind #6's verdict (needs results/ unpacked)
python Other/analysis/exp3_step1.py     # #7
python Other/analysis/exp5_step1.py     # #9
python Other/analysis/exp4_step1.py     # #8 (on branch 8-exp4-analysis)
python Other/analysis/exp1_step1.py     # #5 (on branch 5-exp1-analysis)
```

The `exp<N>_layout_preview.py` scripts redraw each proposed panel from measured data; they are previews of the
layout, never a paper figure.


## 9. Progress log

| Done | What | Commit |
|---|---|---|
| S1 | anchoring out of the Phase 4 **and** Phase 5 crypto timers (`flush_anchors`) | `8f984ba` |
| S2 | Phase 4 stops re-hashing the STARK proof | `8f984ba` |
| S4 | every transition's PQCH check as one `verify_many` matrix product | `5a699e7` |
| S3a | authorization node's χ(v) keyed by BID | `5a699e7` |
| S6 | `finalize_gas` / `rai_gas` recorded in Exp. 5 | `d0012eb` |
| S5 | **withdrawn** — the S34/S99 zeros are deliberate; it is `AuthCost`'s vocabulary that is short | `d0012eb` |
| S7 | σ_b signs `H(r_b)`, hashed once at checkpoint time (replaces P7) | `c98401e` |
| P1 | **FreshLeaf** — `leaf_digest` / `state_digest` split, `fresh_leaf` used in Phases 3, 4 and 5, `v_snap` in PBRP and checked in Phase 6, `veredact.snapshot_window_k` | `8b93387` |
| §4 Exp. 1 | 20 % stale + absent workload (`fault_fraction`, `fault_kinds`), a stale request fails FreshLeaf for real (no tamper flag), `invalid_accepted` metric, variants dropped (Ppdfd), rates 25–1,000, one-panel Fig. 3 | `25e33fa` (branch `13-experiment-redesigns`, Ppdfd) |
| §4 Exp. 2 | Re-ZK dropped, n ∈ {4 … 64}, one panel of complete cost vs n | `caea15d` |
| §4 Exp. 3 | `end_to_end_ms` (generation + verification per query), one panel | `0a0f659` |
| §4 Exp. 5 | anchor `txlog`; each Exp. 1 point records its anchoring tx/bytes/gas; Fig. 7 = transactions per finalized redaction for every system; Exp. 5 run keeps the \|Ω_e\| ∈ {1, 8, 32, 64, 128} sweep for the text | `81d3be7` |
| §4 Exp. 4 | #8 change 3: real substituted (another record's genuine evidence) and stale (a genuine earlier checkpoint) faults; fixed `verify_audit` raising on evidence from another authorization batch | `09521d6` |
| P2 | **BatchAttest** — one VPS signature per admission window (`veredact.vps_window` W = 256, `vps_window_ms` = 500); alpha_i = window root + path (`Attestation`), also the receipt; Phase 4 closes a still-open window of a selected request; SAVER verifies each window signature once per query (`nodes_win`), Shared-Evidence / Per-Record per record; response size counts one root + signature per window | `ceefbd0` |
| P3 + P4 | **Anchored checkpoint digest + RoundCheckpoint** — every A_b carries h_b^CP (`Ledger.checkpoint_digest`), stored on the chain beside MR_b (`cpDigest`, event `CheckpointAnchored(b, vb, mr, cpDigest)`); Phase 5 checkpoints have no signature of their own, the checkpoint authority signs the round's Merkle root once (`Ledger.round_checkpoint`, `finalizeRedaction(bid, bs, cps, roundRoot, roundSig)`); the audit recomputes h_b^CP and compares it with the chain, no checkpoint signature in the response; Phase 2 checkpoints keep their own signature (`initialSigs`). **Contract changed: rebuild the image before any run.** A test compiles the contract with solc 0.8.24 | `4b012af` |
| S3b | **Shared nodes by id** — the response carries each transition node once and a record references it (`_node_ref`); the auditor computes a node's identity (hashing the 64 KiB r_b') once per distinct node in SAVER and Shared-Evidence, per record in Per-Record (which duplicates the evidence); a record with any other evidence is its own node | `bbfe072` |
| P6 | **PQCH for the old and the new state** (paper-conformance gap #1 closed): PBRP carries r_b; `_pqch_batch` checks two columns per transition in one batched product; T_CH = 2 per distinct transition (SAVER) or per record (variants). Lands after S4 + S3a + S3b as planned | `28c0e98` |
| Fairness | **Committee members in parallel + real message delay**, for every threshold scheme alike (`methods/committee.py`, config `committee`): each member's work timed on its own, a step's crypto time counts the slowest member; each committee message round really waits 10 ms (= `ledger.netem_delay_ms`), reported as network time (`net_ms`, Exp. 1 `redact_net_ms`), never as crypto. Rounds: VeRedact-PQ 2 per authorization round (approvals, PQCH shares); S1 2 per redaction (node checks, collision partials; Li et al. Sec. III-B3, V-B); S27 2 per redaction (Adapt's CA rounds; Liu et al. Sec. VI). S34 and S13 have no committee step | branch `13-committee-fairness` |

**Not run:** `make test`. It is forwarded to the AWS server by `deploy/aws/remote.sh`, which needs jaoguya's
yes. Only `ruff check` and `ruff format --check` were run locally, with the arguments CI uses. The 15 tests
added here have never been executed.

**Manuscript:** P1's text already exists in red at `suggest_change/exp1/VeRedact-optimize2.tex` (#5 step 3).
One thing the implementation adds that the tex does not yet say: the anchored snapshots are kept per batch
(`Ledger.snaps`) and the window k is applied by the predicate, so k is a protocol parameter and the list is
an implementation detail. Nothing else in `Overleaf/` is touched, per the one-merge-at-the-end rule.
