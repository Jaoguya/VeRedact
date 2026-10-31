# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency`, state of 30 October 2026.

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting a machine,
> tests, smoke, reruns, provers, moving or deleting results). One yes covers one action. The full run starts only
> on the exact words **"start full run"**.

**In short:** the code follows the final manuscript `Overleaf/VeRedact-optimize.tex` (accepted as-is: the "Peppo
Implementation Strategy"). **No experiment has been run with the new code yet.** The author's limits: **no spot**,
**only machines the author owns and controls (AWS, nothing local or third-party)**, **budget US$50**. The plan is
open (section 5): recommended **O2**, one run on veredact-bench plus on-demand provers sized to the request rate
(~US$30–37, ~12–17 h, needs new code).

## 1. What the project is

VeRedact-PQ is a scheme for a **redactable blockchain** (a recorded transaction can later be edited or erased under
strict auditable rules), built on **post-quantum** cryptography. The paper compares it with earlier schemes
(**baselines**) and its own **ablation variants**; this repository measures all of them on the same machine and data.

| Name in code | Paper ref. | What it is |
|---|---|---|
| `veredact` | this paper | CORA selection + SFMR execution + SAVER audit, post-quantum throughout |
| `veredact-per-request` / `-fixed-batch` / `-cora-no-sfmr` | Exp. 1 variants | no batching / arrival order, size 64 / CORA but one adaptation per request |
| `veredact-re-zk` | Exp. 2 variant | every committee member re-verifies each PQZK proof |
| `veredact-shared-evidence` / `-per-record` | Exp. 3 variants | shared evidence per record / complete evidence per record |
| `S1` / `S13` / `S27` / `S34` | [1] / [13] / [27] / [34] | Improved DCH / EAQ-VRBC / ETCH / CHET |
| `S99` | — | LETA; kept in Exp. 0 and 2 by the author |

Where things live: `Benchmark/` (code, configs, deploy, tests; results in `Benchmark/results/` on the server),
`Result/` (figures, still old), `Overleaf/VeRedact-optimize.tex` (edited only when the author asks),
`Other/docs/` (experiments, paper conformance, baselines), `TASK.md` (task log; last lines = open items).

Server: **veredact-bench** (Singapore, r7i.4xlarge, 16 vCPU, 128 GB, ~US$1.28/h) with a private Besu QBFT chain;
powers off 30 min after idle. Commands go through `Benchmark/deploy/aws/remote.sh`; never compute on the laptop.

## 2. The experiments

| Exp. | Question | x-axis | Systems |
|---|---|---|---|
| 0 | Cost of each building block | — (table) | all, incl. S99 |
| 1 | Throughput, p95 latency, execution sharing (CORA discovers, SFMR realizes) | rate 100–5,000 req/s; Zipf skew | veredact + 3 variants, S1, S13, S27, S34 |
| 2 | Phase 4 authorization per request and per set | committee 4–32; set size 1–256 | veredact, re-zk, S1, S34, S99 |
| 3 | Audit with shared evidence | n_Q 10–10^4; records per batch 1, 8, 64 | veredact, shared-evidence, per-record, S1, S13 |
| 4 | Selective PQZK escalation; fault isolation | escalation 0–100 %; faults 1–10 % | veredact, S1, S13 |
| 5 | Checkpoint size and finalization latency (PBN) | affected batches 1–32; validators 4, 7, 10 | veredact |

Scale: 10^5-transaction ledger, n_Q up to 10^4, 30 samples per point. The manuscript currently says **three runs**
(mean over runs, 95 % CI, t with 2 df); a one-run plan needs that sentence reverted (only when the author asks).

## 3. Why the prover machines exist

- **Verifier ≠ prover.** The pass/reject check (PQZK.Verify, ~0.7 ms) runs on the measured server and is timed.
- **Creating** each proof (PQZK.Prove, ~23 ms median, ~30 ms mean) is the requester's job; the paper excludes it from
  server time (manuscript l. 2789).
- At 5,000 req/s that is ~150 cores of proving; on the measured server it slowed VeRedact-PQ 4× (82 → 338 ms per
  round), and 4 local cores cap at ~270 proofs/s. So separate machines act as the requesters' own computers.
- **Cannot be avoided:** proofs are bound to the request, state h_st and epoch (`veredact.py:98`, `:157`), so no
  precomputing, reuse or fakes (fakes are rejected; skipping the check is cheating). Simulating or a laptop prover
  were rejected (not real; laptop: ~200–270 proofs/s, 30–50 ms network bias, not under the author's control).
- Only VeRedact-PQ needs provers; the baselines have no zero-knowledge proof.

## 4. Status

| Item | State |
|---|---|
| Code | 105 tests pass (image builder, 1b83d44); smoke of the split run: 12 of 13 parts exit 0, e1 not run; 7 bugs fixed (b41848b) |
| Results with the new code | **none** |
| Spot attempt (30 Oct) | no spot for any 384-vCPU prover pool in us-east-2: nothing started (~US$2.3) |
| On-demand switch | committed and pushed (`d6f70b8`): `configs/aws.toml [run] market`, used by `provision_workers.sh` / `provision_provers.sh` (split run) and `provision_provers_local.sh` (one-server run, O2) |
| AWS leftovers | image ami-083cb25ef0de5032b + snap-0de92fbdcccc2a935 in us-east-2 (~US$5/month); delete with `teardown_workers.sh` when not needed (ask) |
| Spent this session (approx.) | veredact-bench idle leak from a test ~US$47 (fixed: killpg in `test_fidelity.py`), smoke ~US$14, spot attempt ~US$2.3, images ~US$1.3 |

## 5. Decisions needed from the author

**Code reading of 31 Oct (facts, not choices) — O2 as written is not available:**
- The published latency is **arrival -> finalized** (`summaries._exp01`, `_e2e_latency_ms`; the "from submit"
  variant was rejected because "it hides client-side waiting"). The wait for a free prover sits in that interval,
  so a prover pool that changes between points puts a step into Fig. 3 that is an artefact, not a measurement.
- The rate sweep is *inside* the per-system loop (`exp01.run`), while `Results.begin/end` checkpoints per
  (experiment, system) and `begin()` deletes the folder. Rates therefore cannot be split over separate runs, so
  rate-sizing needs either the measuring process to drive AWS mid-experiment or a rework of the results layer.
- Provers are up only for step 1 of `full_run.sh` (the 4 systems that prove), **~1.7 h**, not the whole run.
- One `c7i.48xlarge` is 192 cores (`prover_service.py --workers` = `os.cpu_count()`) against ~150 core-s/s at
  5,000 req/s. Prover-bound shows as `submitted_on_time` falling while decided/offered stays high; note that
  `check_coverage.py` does NOT fail on it — a saturated point still has a value.

**D1. Run plan within US$50 (no spot). Whichever is chosen, the prover count stays the same for every point:**

| Plan | What | Runs | Time | Cost (estimate) | Code |
|---|---|---|---|---|---|
| **P1** | one server, **1 prover** (`PROVER_COUNT=1`) | 1 | ~12–17 h | ~US$35–42 | none |
| **P2** | one server, **2 provers** (today's default) | 1 | ~12–17 h | ~US$55–61 (over budget) | none |
| P3 | 3 repetitions on one server (`rep_sequence.sh`) | 3 | ~36–51 h | ~US$105–124 (over budget) | fix rep_sequence (below) |
| Split, 3 runs on demand | 14 workers + 2 prover pairs, us-east-2 | 3 | ~8 h | ~US$145–160 (over budget) | none |
| ~~O2~~ | rate-sized prover pool | — | — | — | not available (see above) |
| O3 | no provers | — | — | — | not allowed (capped / unfair) |

P1 vs P2 is open: 1 prover may be enough. It is decided by one number in the run's own log, so P1 can be tried
first and the affected system rerun with `PROVER_COUNT=2` if it comes out prover-bound.

**D1b. One run vs three (the manuscript says three; section 2).** In one run a latency point already has
6,000–300,000 requests as samples, but `throughput_per_s` is a **single** number per point — that is the figure
that has no replication. Options, cheapest first:

| Option | What | Cost | Note |
|---|---|---|---|
| **A** | throughput CI from sub-windows of the 60 s window (n=6 per point) | **US$0** | post-processing of the stored rows |
| **B** | bootstrap CI for p95 (`metrics.ci95_halfwidth` covers the MEAN only) | **US$0** | post-processing |
| C | repeat only the headline points with 2 more seeds (`VRPQ_REP=2,3`; seed += (r-1)*1000, rep 1 = the single run) | ~US$6–10 | reported as a robustness check, not as the CI |
| D | three full runs | ~US$105–124 | over budget |

A and B are retroactive: `scripts/resummarize.py` recomputes `metrics.json` from the stored `rows.csv`, so a
single run can be paid for now and the statistics added later without paying AWS again. A one-run plan still
needs the manuscript's "three runs ... 95 % CI (t, 2 df)" sentence changed — author only.

**D2. Make proving itself faster (fewer prover machines):**

| Option | Change | Gain (estimate, not measured) | Conflict |
|---|---|---|---|
| **1 (recommended first)** | build the STARK with `target-cpu=native`; same logic, same proofs | ~10–30 % | none; measure first (~15 min, ~US$1, needs a yes) |
| 2 | field f128 → f64 (Goldilocks) in winterfell; rewrite AIR + Rescue | ~2–4× | breaks Peppo (code as-is); Exp. 0 T_ZP/T_ZV change |
| 3 | smaller credential registry (`registry_depth` 15 → less) | ∝ trace length | changes a system parameter |
| — | blowup 8 → 4 | not possible: Rescue α = 5 needs blowup 8 | — |

**D3. Older open points:** S13's audit witnesses timed 8 at a time (3–7 % against S13: re-time or disclose);
bursty workload not implemented; the paper does not name the prover machines (author writes it in Overleaf).

**D4. `rep_sequence.sh` is stale** (only matters for P3): its step 1 gives provers to `veredact` alone
(`SYSTEMS=veredact`, and it skips only `exp01:veredact` afterwards), so the three Exp. 1 variants would run in
step 2 **without** provers and come out client-bound (~270 proofs/s locally). `full_run.sh` passes all four
(`VRPQ_EXP1`). It also still defaults to `PROVER_COUNT=2`. Fix before choosing P3.

## 6. Next steps (each AWS step needs the author's yes)

1. Author picks D1 (and D2).
2. For O2: write the rate-sized prover pool; tests on the server; rebuild the image if workers are used.
3. Smoke test of the chosen plan (smoke numbers are never results).
4. On "start full run": run; check logs after ~15 min; collect, aggregate, tables, figures; tear down.
5. The author writes the results text in Overleaf.

Commands of the split run: `deploy/aws/build_image.sh`, `provision_workers.sh <n>`, `launch_reps.sh <runs>`,
`collect_reps.sh <runs>`, `teardown_workers.sh` (`TIER=smoke` for the smoke; `ONLY="<n>" FORCE=--force` reruns a
part). One-server run: `deploy/experiments/full_run.sh`.

## 7. What to read, in order

1. `TASK.md`, last 20 lines. 2. `Other/docs/experiments.md`. 3. Manuscript, Section Evaluation.
4. `Other/docs/aws-runbook.md`. 5. `Benchmark/src/veredact_bench/utils/run_plan.py`, `deploy/experiments/rep_run.sh`,
`deploy/aws/launch_reps.sh`. 6. `Benchmark/configs/aws.toml [run]`, `configs/experiments/*.yaml`.

## 8. House rules

- Ask before running anything on AWS; one yes per action; full run only on "start full run".
- No capped results; never simulate, extrapolate or reuse timings; same hardware for every scheme of an experiment.
- Only this project's AWS resources (never SSO, test-, Apichon-Ubuntu, siemcrypt-eval; in us-east-2 never
  pqbvcd, starfish, des431, snap-0b10404f5d9db0a37, snap-055db4676f7f6676b).
- Never edit the manuscript unless the author asks. Smoke numbers are never results. Verify a cause before claiming it.
- Lean workspace, short comments, one line per task in `TASK.md`. Ask before changing stale docs. Commit/push only when asked.
- Every run gets a hard time limit; after any test, check that veredact-bench powered off.

## 9. Glossary

- **Prover**: machine that creates VeRedact-PQ requesters' zero-knowledge proofs (load generator, not timed).
- **Verifier**: the server-side pass/reject check of a proof (timed).
- **Spot**: cheaper AWS machine AWS may take back; not used (author, 30 Oct).
- **On-demand**: normal AWS machine at full price, never taken back.
- **Capped value**: a value cut off by a limit; never reported.
- **History**: redactions audited in Exp. 3–4, built before the timed audits.
