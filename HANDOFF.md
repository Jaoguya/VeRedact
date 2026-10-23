# Handoff — VeRedact-PQ benchmark

Branch `s99-leta-exp1-latency`, state of 23 October 2026.

> **Do not run anything on AWS without the author's explicit yes for that specific action** (booting the
> server, tests there, reruns, prover machines, moving or deleting results). One yes covers one action.

**In short:** every experiment has run once at the final scale. VeRedact-PQ's Experiment 4 was rerun after a bug
fix and its result has not been read yet. Experiment 1 was re-planned on 23 Oct (new rates, latency drawn only
where fully measured, see §4.2); the code is ready, the rerun of S1, S13 and S34 is not done yet. Everything else
is done, and most of the paper's results section is already updated.

## 1. What the project is

VeRedact-PQ is a scheme for a **redactable blockchain** (a recorded transaction can later be edited or erased,
e.g. to remove personal data, under strict auditable rules), built on **post-quantum** cryptography. The paper
compares it with earlier schemes (**baselines**); this repository measures all of them on the same machine and
data.

| Name in code | Paper ref. | What it is |
|---|---|---|
| `veredact` | this paper | post-quantum, committee-authorized, batched redaction with auditable records |
| `S1` | [1] | Improved decentralized chameleon hash on Jia's chain (classical) |
| `S13` | [13] | EAQ-VRBC: identity tags + RSA accumulator; compact audit proofs |
| `S27` | [27] | ETCH: lightweight threshold chameleon hash (fastest redaction) |
| `S34` | [34] | CHET with attribute-based policies (slow per redaction) |
| `S99` | [39] | LETA: post-quantum batch authentication, authorization comparison only |

Where things live:
- `Benchmark/` — code, configs, deploy scripts, tests; raw results in `Benchmark/results/` (not in git).
- `Result/Pdf`, `Result/Picture` — generated figures.
- `Overleaf/` — manuscript. `VeRedact-2.tex` is final and never edited; changes go into
  `Overleaf/revised/VeRedact-2-blue.tex` inside `\chg{…}` (printed blue).
- `Other/docs/` — `experiments.md` and one note per baseline in `baselines/`.
- `TASK.md` — log of every task and where its result is; the last lines list what is open.

Where it runs: one AWS server **veredact-bench** (r7i.4xlarge, 16 vCPU, 128 GB, ~US$1.28/h) with a private
7-node Hyperledger Besu blockchain on it. Only VeRedact-PQ's Experiment 1 also uses two large spot **prover**
machines (they generate the requesters' zero-knowledge proofs). Commands go through
`Benchmark/deploy/aws/remote.sh`. The AWS account holds other people's machines: touch only veredact-bench and
the prover/worker machines the experiments create.

## 2. The six experiments

| Exp. | Question | x-axis | Schemes |
|---|---|---|---|
| 0 | How long does each cryptographic building block take? | — (table) | all six |
| 1 | Redactions finished per second, and end-to-end time of one | request rate 100–1,000/s (+ low rates for S1, S13, S34); data skew | veredact, S1, S13, S27, S34 |
| 2 | How long does authorizing a request take? | committee 4–32; batch 1–256 | veredact, S1, S34, S99 |
| 3 | How fast is an audit answered, how big is the answer? | records audited n_Q 10–10^5 | veredact, S1, S13 |
| 4 | How long does the auditor verify it; are tampered records caught? | n_Q 10–10^5 | veredact, S1, S13 |
| 5 | Blockchain gas per redaction | batch 1–256 | veredact, S1, S13, S27, S34 |

A scheme is missing from an experiment only when its paper defines no such step. Scale: 10^6-transaction
synthetic ledger, one run, 30 samples per point (5 at the most expensive). Experiments 3–4 audit the same
pre-built history (~100,000 redactions) for every scheme; it is saved on the server (`results/_histories/`).

## 3. Status

full = fully measured, partial = some values are lower bounds, pending = result not read, — = not in it.

| Scheme | Exp. 0 | Exp. 1 | Exp. 2 | Exp. 3 | Exp. 4 | Exp. 5 |
|---|---|---|---|---|---|---|
| veredact | full | partial | full | full | **pending** | full |
| S1 | full | partial | full | full | full | full |
| S13 | full | partial | — | full | full | full |
| S27 | full | partial | — | — | — | full |
| S34 | full | partial | full | — | — | full |
| S99 | full | — | full | — | — | — |

- Manuscript: blue copy has the new numbers for Experiments 0, 1, 2, 3, 5 and both tables; Experiment 4's
  paragraph and figure are still from an older run.
- Experiment 1 throughput is full everywhere; only its latency is partial.
- Server stopped, nothing running. Cost of the final run series ~US$67; October ~US$225.
- Commits `1645d0c` (cleanup) and the 23 Oct Exp. 1 change are pushed; their tests have not been run yet (they run on
  the server).

## 4. Open problems

1. **Experiment 4 rerun not read.** VeRedact-PQ's auditor searched the whole chain from the start, so its cost
   grew with the chain's age. It now reads only the blocks where its records were written (tested on real
   Besu), and its Experiment 4 was rerun. The server then powered off; whether the rerun finished is unknown.
   Log on the server: `Benchmark/results/logs/exp4_rerun_20261021.out`.
2. **Experiment 1 latency was a lower bound above capacity — fix decided 23 Oct (author: option A), code done,
   rerun pending.** Requests arrive for 60 s, then the run waits 30 s; a request unfinished at the stop only gives
   a lower bound (~87 s for every overloaded scheme). Capacity (10^6 run, from the blue text; confirm from
   `metrics.json`): S27 ~130–145/s, VeRedact-PQ ~100–140/s, S1 ~65–72/s, S34 ~6/s, S13 ~5/s.
   What changed (`configs/experiments/exp01_redaction_throughput.yaml`, `utils/config.py: exp1_rates`):
   - shared rates now 100, 250, 500, 1,000 req/s; 2,000 and 5,000 dropped (every scheme saturates by 500; above
     1,000 the provers could not deliver the load to VeRedact-PQ). Manuscript range changed to match.
   - `low_rates` at ~20–80 % of capacity: S1 25, 50; S13 and S34 1, 2, 4 req/s.
   - Fig. 3(b) draws a latency point only if >= 95 % of its requests finished (no hollow lower-bound markers);
     both panels show only configured rates, so veredact and S27 need no rerun.
   - Blue manuscript: Exp. 1 setup sentence and caption updated; the two results paragraphs are still the old
     100–5,000 text (`% TODO` above them) — rewrite after the rerun.
   To do: rerun Exp. 1 for S1, S13, S34 only (`--systems S1,S13,S34 --force`, ~3–4 h, ~US$5–6).
3. **S13 at 5,000 req/s stopped late** (386 s instead of ~100 s): client threads were joined one after another,
   each with its own 30 s timeout. **Fixed 23 Oct**: `join_by` gives them one shared deadline; test
   `test_exp1_clients_share_one_deadline`. Throughput was never affected (it counts only the window).
4. **VeRedact-PQ's provers lagged at 2,000 and 5,000 req/s** — no longer in the paper: those rates were dropped.
5. **S13's audit times are 3–7% high**: its witnesses are timed 8 at a time on separate cores; the bias is
   against S13.
6. **VeRedact-PQ's gas rose, cause unverified**: likely more distinct transaction batches touched per round
   with the larger ledger; not counted yet.
7. **Saved histories will be rebuilt**: they are reused only if the code that builds them is byte-identical;
   the cleanup edited comments there, so the next run rebuilds VeRedact-PQ's (~1 h). S1's and S13's were already
   outdated by the Experiment 4 fix.
8. **Housekeeping**: 14 old files from 29 Sep in the root of `Benchmark/results/` on the server should move to a
   `_superseded` folder (not deleted). Checked 23 Oct: the laptop's `Benchmark/results/` is empty and the laptop's
   git stash is empty, so nothing is left to do locally.

## 5. Decisions needed from the author

- **A. Experiment 1 latency — decided 23 Oct**: latency only where fully measured, low rates added (§4.2).
- **B. S13 witnesses.** Re-time one at a time (removes the bias, ~8x longer for that step), or keep and state
  the bias in one sentence.
- **C. VeRedact-PQ provers at high rates — resolved 23 Oct** by dropping 2,000 and 5,000 req/s.
- **D. S13.** Recommended: keep it (dropping it leaves the other problems and weakens Experiments 3–4).
- **E. Housekeeping.** Move old result files aside on the server (one server boot); make the saved-history check
  ignore comments (triggers one rebuild now).

## 6. What to do next (each AWS step needs a yes first)

1. One server boot (~30–45 min, ~US$1): read the Experiment 4 rerun log; fetch its results if finished; run
   `remote.sh '.venv/bin/ruff check src scripts tests && .venv/bin/python -m pytest -q'`; count batches per round
   for the gas question.
2. If the rerun did not finish: propose rerunning VeRedact-PQ's Experiment 4 (~2–3 h incl. history rebuild).
3. Write Experiment 4 into the blue manuscript, copy its figure next to the tex, re-extract
   `perf_analysis_blue.tex`, compile on the server.
4. Experiment 1 (code done 23 Oct): in the same boot confirm S1/S13/S34 capacities from `metrics.json` (adjust
   `low_rates` if one is lower), then with a yes rerun `--systems S1,S13,S34 --force`; regenerate Fig. 3 and
   rewrite the two Exp. 1 results paragraphs in the blue manuscript (+ `perf_analysis_blue.tex`).
5. After B: rerun only the affected part, or add the one-sentence disclosure.
6. Finally: `scripts/check_coverage.py --tier experiment`, tables and figures, one line in `TASK.md`, commit,
   push.

## 7. What to read, in order

1. `TASK.md`, last 20 lines.
2. `Other/docs/experiments.md`.
3. `Overleaf/revised/perf_analysis_blue.tex` (the results section as the paper says it now).
4. `Other/docs/aws-runbook.md`.
5. `Other/docs/baselines/*.md`.
6. `Benchmark/deploy/experiments/full_run.sh` (`RESUME=1` finishes a stopped run without provers).
7. `Benchmark/configs/experiments/*.yaml`.
8. `Benchmark/results/logs/` (durations: `=== <exp> done in`, `<exp> <scheme>: N rows in`).

## 8. House rules

- Ask before running anything on AWS; one yes per action.
- No capped results: report a value only if it is a full measurement.
- Never cheat to save cost: no simulated, extrapolated or reused timings; same hardware for every scheme.
- Only this project's AWS resources.
- Never edit `Overleaf/VeRedact-2.tex`; changes go into the blue copy inside `\chg{…}`.
- Smoke and pilot numbers are never results.
- Verify a cause before claiming it.
- Lean workspace: extend existing scripts and docs, short comments, one line per task in `TASK.md`.
- Ask before changing outdated docs. Commit or push only when asked.
- Every run gets a hard time limit (`sudo shutdown -h +<minutes>`); the server also powers off 30 min after idle.

## 9. Glossary

- **Redaction**: editing or erasing a transaction already on the chain without breaking it.
- **Chameleon hash**: a hash whose secret-key holder can find a second input with the same hash.
- **Post-quantum**: cryptography meant to resist quantum computers (here ML-DSA-65 and lattice-based hashes).
- **Gas**: the blockchain's unit of on-chain computation and storage cost.
- **Audit, n_Q**: an auditor asks which redactions happened and checks the evidence; n_Q = records returned.
- **Prover**: machine that makes the zero-knowledge proofs VeRedact-PQ's requesters attach.
- **Saturated / overloaded**: requests arrive faster than the scheme finishes them.
- **Lower bound / capped value**: latency counted only until the measurement stopped; the real value is higher.
- **Saved history**: the pre-built ~100,000 redactions audited in Experiments 3–4, saved on the server.
- **Besu**: the Ethereum client running the private test chain.
- **Spot instance**: a cheaper AWS machine that AWS may take back at short notice.
