---
name: aws-cost
description: Use when planning or proposing any AWS run, boot, rerun or resource change for the VeRedact experiments, or answering a cost question. Finds the cheapest honest option for THIS project and proposes it as choices.
---

# AWS cost for the VeRedact experiments

Scope and asking first are in memory (aws-hands-off-instances, ask-before-running, compute-on-aws-only).

## Integrity first
A saving is valid only if every reported number stays a true, uncapped measurement. Never simulate,
extrapolate or reuse a timed result (only untimed setup, e.g. saved histories); never drop samples, schemes or
points; never give one scheme different hardware; never quote probe or smoke numbers or under-report cost.
If an option touches what is measured, say so in it.

## Find the saving
- **Estimate from logs, never guess**: `=== <exp> done in`, `<exp> <scheme>: N rows in`, peak memory in
  `Benchmark/results/logs/`; disk from `df` / `du results/`.
- **Instance type**: least vCPU/memory that holds the measured peak; same host type for every scheme.
- **Purchase option**: on demand only (author 2026-10-30: no spot).
- **Hours**: only missing parts (`ONLY="<worker n>" FORCE=--force deploy/aws/launch_reps.sh 3`); reuse saved histories (changes in
  methods/, data/, anchor.py, common.py, history_cache.py, contracts/ force a rebuild: batch them); probe or
  smoke before the full run; provers only for VeRedact-PQ's Exp. 1.
- **Storage**: least gp3 size for results + `_histories` + Docker; list this project's AMIs, snapshots and
  unattached volumes and propose removing unused ones; never copy `_histories` to the laptop.
- **Idle**: hard cap on every run (~1.5x estimate); one boot per check (>= 30 min each); no load in timed phases.

## Propose and report
- 2-4 options, recommended first: time, cost, effect on measurement. A team member decides, as a yes comment on the issue (one yes, one action).
- Cost: this project's usage types only (the account bills others too); billed (Cost Explorer lags ~1 day) vs
  estimated. Rates (on demand): veredact-bench r7i.4xlarge ~US$1.28/h (Singapore); us-east-2 workers m7i.4xlarge
  US$0.806/h, prover c8g.48xlarge US$7.63/h. Budget: US$50.
