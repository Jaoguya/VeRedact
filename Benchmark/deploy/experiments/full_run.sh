#!/usr/bin/env bash
# The paper's full run, end to end on the server (no laptop needed once started):
#   1. VeRedact-PQ's Exp. 1 (and its three Exp. 1 variants) with the remote prover hosts (VRPQ_PROVERS / VRPQ_PROVER_KEY in the environment);
#      the provers terminate themselves 15 min after this step (deploy/server/prover_watchdog.sh)
#   2. every other (experiment, system) of the experiment tier (finished ones are skipped)
#   3. scripts/check_coverage.py --tier experiment (no capped line), tables + figures
#   4. power off (the idle watchdog is the fallback)
# Usage (server): deploy/experiments/full_run.sh   (or give VRPQ_PROVERS/VRPQ_PROVER_KEY of running provers)
#   RESUME=1: skip step 1 (no provers), e.g. to finish a run stopped by its hard cap
set -uo pipefail
cd "$(dirname "$0")/../.."
echo "full run start $(date -u +%FT%TZ)"
# step 1: VeRedact-PQ's Exp. 1 systems (VRPQ_EXP1) with remote prover hosts. Given (VRPQ_PROVERS) or launched here with the
# instance's IAM role and terminated right after; if they cannot be launched, the step is SKIPPED (no silent
# fallback to the load-generator-bound local mode) and the coverage check below reports the missing points.
VRPQ_EXP1=veredact,veredact-per-request,veredact-fixed-batch,veredact-cora-no-sfmr  # every system that proves
LAUNCHED=0
if [[ "${RESUME:-0}" == 1 ]]; then
  echo "STEP1: skipped (RESUME=1)"
elif [[ -z "${VRPQ_PROVERS:-}" ]]; then
  if deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}"; then
    export VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)
    LAUNCHED=1
  else
    echo "STEP1: prover hosts could not be launched - VeRedact-PQ's Exp. 1 is NOT run (see coverage gaps)"
    deploy/server/teardown_provers_local.sh
  fi
fi
if [[ "${RESUME:-0}" != 1 && -n "${VRPQ_PROVERS:-}" ]]; then
  SYSTEMS=$VRPQ_EXP1 deploy/experiments/run_experiments.sh experiment exp01_redaction_throughput
  echo "STEP1_EXIT=$?"
fi
(( LAUNCHED )) && deploy/server/teardown_provers_local.sh   # they also self-terminate 15 min after use
unset VRPQ_PROVERS VRPQ_PROVER_KEY
# step 2 never runs VeRedact-PQ's Exp. 1 systems: step 1 owns them (done with provers, or deliberately missing)
VRPQ_SKIP=$(sed 's/[^,]*/exp01_redaction_throughput:&/g' <<< "$VRPQ_EXP1") deploy/experiments/run_experiments.sh experiment all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment
echo "COV_EXIT=$?"
.venv/bin/python scripts/make_tables.py --tier experiment; echo "TABLES_EXIT=$?"
.venv/bin/python scripts/make_figures.py --tier experiment; echo "FIGURES_EXIT=$?"
echo "full run end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-full-run-done
