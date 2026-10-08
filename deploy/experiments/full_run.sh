#!/usr/bin/env bash
# The paper's full run, end to end on the server (no laptop needed once started):
#   1. VeRedact-PQ's Exp. 1 with the remote prover hosts (VRPQ_PROVERS / VRPQ_PROVER_KEY in the environment);
#      the provers terminate themselves 15 min after this step (deploy/server/prover_watchdog.sh)
#   2. every other (experiment, system) of the experiment tier (finished ones are skipped)
#   3. scripts/check_coverage.py --tier experiment (no capped line), tables + figures
#   4. power off (the idle watchdog is the fallback)
# Usage (server): deploy/experiments/full_run.sh   (or give VRPQ_PROVERS/VRPQ_PROVER_KEY of running provers)
set -uo pipefail
cd "$(dirname "$0")/../.."
echo "full run start $(date -u +%FT%TZ)"
# step 1: VeRedact-PQ's Exp. 1 with remote prover hosts. Given (VRPQ_PROVERS) or launched here with the
# instance's IAM role and terminated right after; if they cannot be launched, the step is SKIPPED (no silent
# fallback to the load-generator-bound local mode) and the coverage check below reports the missing points.
LAUNCHED=0
if [[ -z "${VRPQ_PROVERS:-}" ]]; then
  if deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}"; then
    export VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)
    LAUNCHED=1
  else
    echo "STEP1: prover hosts could not be launched - VeRedact-PQ's Exp. 1 is NOT run (see coverage gaps)"
    deploy/server/teardown_provers_local.sh
  fi
fi
if [[ -n "${VRPQ_PROVERS:-}" ]]; then
  SYSTEMS=veredact deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
  echo "STEP1_EXIT=$?"
fi
(( LAUNCHED )) && deploy/server/teardown_provers_local.sh   # they also self-terminate 15 min after use
unset VRPQ_PROVERS VRPQ_PROVER_KEY
# step 2 never runs VeRedact-PQ's Exp. 1: step 1 owns it (done with provers, or deliberately missing)
VRPQ_SKIP=exp01_redaction_throughput:veredact deploy/experiments/run_experiments.sh experiment all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment
echo "COV_EXIT=$?"
echo "full run end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-full-run-done
