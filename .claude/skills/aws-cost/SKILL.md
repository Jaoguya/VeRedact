---
name: aws-cost
description: Use BEFORE and DURING any AWS action in the VeRedact project — launching, resuming or extending a run, starting/booting veredact-bench, provers or workers, running tests/scripts on the server, fetching results, or answering a cost question. Keeps AWS spend minimal without changing what is measured.
---

# AWS cost discipline (VeRedact benchmark)

Goal: the cheapest way to get the same measurement. Never trade measurement validity for cost
(e.g. a bigger or extra host that makes one scheme faster than its baseline is NOT a saving).

## Scope (hard rule)
- Act only on veredact-bench (`Benchmark/deploy/aws/.instance`) and experiment-created resources
  (veredact-prover, worker hosts). Never touch SSO, test-, Apichon-Ubuntu, siemcrypt-eval or anyone else's machines.
- The account bills other people's resources too: report only this project's usage types
  (r7i/c7i BoxUsage, SpotUsage c7i.48xlarge, our EBS), never the account total as "our cost".

## Before launching anything
1. **Estimate from measured durations, not guesses**: read the per-experiment / per-scheme times in
   `Benchmark/results/logs/*.log` (`=== <exp> done in`, `<exp> <scheme>: N rows in`) and `TASK.md`.
   Past estimates were 2x too low (S13 audit witnesses, VeRedact-PQ Exp. 4). State time AND cost.
2. **Run only what is missing**: finished (experiment, scheme) points are skipped by the runner; use
   `deploy/experiments/resume_run.sh` (no provers) instead of `full_run.sh` after a stop.
   Move a point aside (`results/_superseded_<date>_<reason>/`) only when it must be re-measured.
3. **Provers only when needed**: only VeRedact-PQ's Exp. 1 needs the c7i.48xlarge prover hosts.
   Spot first (`PROVER_MARKET`, ~US$3/h vs 9.88 on-demand), terminated right after the step.
4. **Reuse saved histories** (`results/_histories/`): untimed setup, loaded when the safeguards match.
   Know that a change in methods/, data/, anchor.py, common.py, history_cache.py or contracts/ changes the
   code digest and forces a rebuild (~1 h VeRedact-PQ, ~5 h S13): batch such code changes before a rerun.
5. **Cheapest check first**: memory probe / smoke / loopback check instead of a full-scale pilot;
   never a pilot with provers unless the prover path itself is under test.
6. **Right-size from data**: choose the instance from a memory probe (peak + margin), not from fear.
   Do not add vCPUs to shorten a run if it changes a timed measurement (S13 witnesses are single-core summed).
7. **Ask the user** before any launch whose estimate exceeds the last approved budget.

## While running
- **Always a hard cap**: `sudo shutdown -h +<min>` sized ~1.5x the estimate; the run script powers off
  2 min after DONE; the idle watchdog powers off 30 min after the last command. If the estimate grows,
  EXTEND the cap (losing a nearly finished run costs more than an hour of server time).
- **Don't load the server during timed phases** (tests, figures, probes): it distorts timings and may force
  a rerun. Use untimed phases (history build) or wait for the end.
- **Checks are cheap only while it runs**: booting a stopped server just to read a log costs at least the
  30-min watchdog. Collect everything needed (log tail, metrics, coverage, summaries) in ONE boot.
- **Background watchers**: poll with ssh every 60 s from the laptop (costs nothing on AWS); refresh the SSH
  rule (`deploy/aws/refresh_ssh_rule.sh`) when the laptop's IP changes.

## After a run
- Confirm nothing is left running: veredact-bench `stopped`, no `veredact-prover*` / worker instance
  `running|pending` (`aws ec2 describe-instances --filters 'Name=tag:Name,Values=veredact-prover*' ...`).
- **Fetch small, not everything**: rsync `results/` with `--exclude _histories --exclude '_superseded_*'`
  (histories are tens of GB and stay on the server); never `fetch_results.sh` blindly.
- Delete superseded server data only when the user asks; disk (EBS) costs little, a lost result costs a rerun.

## Reporting cost
- Server: hours x rate (r7i.4xlarge ~US$1.28/h); provers: hours x 2 x rate (spot ~US$3, on-demand 9.88).
- Cost Explorer lags ~1 day; say which part is billed and which is an estimate.
- Put the estimate and the actual in `TASK.md` with each launch/stop entry.
