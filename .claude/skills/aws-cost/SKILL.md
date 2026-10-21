---
name: aws-cost
description: Use BEFORE and DURING any AWS action in the VeRedact project — planning, launching, resuming or extending a run, booting veredact-bench, provers or workers, running anything on the server, fetching results, or answering a cost question. Finds the cheapest honest way to run THIS project's experiments and proposes it as recommendation choices.
---

# AWS cost for the VeRedact experiments

**Goal**: find the cheapest way to run this project's experiments on AWS, and propose it to the author as
recommendation choices. **Scope**: this project only (veredact-bench `Benchmark/deploy/aws/.instance`, and
the veredact-prover / worker hosts the experiments create). Never act on, or count, anyone else's resources
(SSO, test-, Apichon-Ubuntu, siemcrypt-eval, ...): the account bills them too.

## Integrity comes first (non-negotiable)
A saving is only valid if every reported number stays a true measurement of the real system. Never:
- simulate, extrapolate, cache or reuse a TIMED result (only untimed setup such as saved histories may be
  reused, behind their safeguards); never shorten a window, drop samples, skip a scheme or an x point to save
  money (no capped outputs) unless the author approves and the manuscript says so;
- change hardware so one scheme looks faster than it is (e.g. extra vCPUs for S13's summed single-core
  witnesses, a bigger host for VeRedact-PQ only), or compare schemes measured on different hosts silently;
- quote smoke, pilot or probe numbers as results; hide a failed, capped or partial run; under-report cost.
If the cheapest option touches what is measured, say so in the option, plainly, and let the author choose.

## How to work
1. **Measure before proposing**: durations from `Benchmark/results/logs/*.log` (`=== <exp> done in`,
   `<exp> <scheme>: N rows in`) and `TASK.md`; memory from the memory probe / logged peak memory; disk from
   `df` and `du results/`. My earlier estimates were ~2x too low: never guess.
2. **Look for savings in every cost line**, smallest that still measures correctly:
   - *Instance type (model)*: the least vCPU / memory that holds the measured peak with margin and keeps the
     timed path identical; same CPU family for every scheme.
   - *Purchase option*: spot for hosts whose loss only fails a point loudly (provers: spot first, on-demand
     fallback); on-demand where an interruption would silently bias a measurement.
   - *Hours*: run only missing points (`deploy/experiments/resume_run.sh`), reuse untimed histories, batch code
     changes that would force a history rebuild, use a probe or smoke check instead of a full pilot, launch
     provers only for VeRedact-PQ's Exp. 1 and terminate them right after.
   - *Storage*: the least EBS size and type (gp3) that fits results + saved histories + Docker; list this
     project's AMIs, snapshots and unattached volumes and propose removing the unused ones; never copy saved
     histories to the laptop.
   - *Idle time*: hard cap on every run, idle watchdog, one boot per check (a boot costs >= 30 min).
3. **Propose, don't impose**: present 2-4 choices, recommended first, each with time, cost, and its effect on
   measurement ("none" must be true). The author decides; then record the choice in `TASK.md`.
4. **Ask before**: any launch, any increase over the last approved budget, any deletion (AMI, snapshot,
   volume, results), any change of instance type or purchase option.

## Always, during and after a run
- A hard cap (`sudo shutdown -h +<min>`, ~1.5x the estimate); extend it rather than lose a nearly done run.
- No server load (tests, figures, probes) during a timed phase.
- After: veredact-bench stopped, no `veredact-prover*` / worker instance running or pending, results fetched
  without `_histories` / `_superseded_*`.
- Report cost honestly: this project's usage types only; billed (Cost Explorer lags ~1 day) vs estimated;
  estimate and actual written in `TASK.md`.
