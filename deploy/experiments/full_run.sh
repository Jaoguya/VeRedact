#!/usr/bin/env bash
# The paper's full run, end to end on the server (no laptop needed once started):
#   1. VeRedact-PQ's Exp. 1 with the remote prover hosts (VRPQ_PROVERS / VRPQ_PROVER_KEY in the environment);
#      the provers terminate themselves 15 min after this step (deploy/server/prover_watchdog.sh)
#   2. every other (experiment, system) of the experiment tier (finished ones are skipped)
#   3. scripts/check_coverage.py --tier experiment (no capped line), tables + figures
#   4. power off (the idle watchdog is the fallback)
# Usage (server): VRPQ_PROVERS=ip:7700,... VRPQ_PROVER_KEY=... deploy/experiments/full_run.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
echo "full run start $(date -u +%FT%TZ)"
if [[ -n "${VRPQ_PROVERS:-}" ]]; then
  SYSTEMS=veredact deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
  echo "STEP1_EXIT=$?"
else
  echo "STEP1: no prover hosts given - VeRedact-PQ's Exp. 1 uses local requester processes (A3)"
fi
unset VRPQ_PROVERS VRPQ_PROVER_KEY
deploy/experiments/run_experiments.sh experiment all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment
echo "COV_EXIT=$?"
echo "full run end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-full-run-done
