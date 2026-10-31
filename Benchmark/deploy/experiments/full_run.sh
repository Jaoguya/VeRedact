#!/usr/bin/env bash
# The paper's full run, end to end on the server (no laptop needed once started):
#   1. VeRedact-PQ's Exp. 1 (and its three Exp. 1 variants) with the remote prover hosts (VRPQ_PROVERS / VRPQ_PROVER_KEY in the environment);
#      the provers terminate themselves 15 min after this step (deploy/server/prover_watchdog.sh)
#   2. every other (experiment, system) of the experiment tier (finished ones are skipped)
#   3. scripts/check_coverage.py --tier "$TIER" (no capped line), tables + figures
#   4. power off (the idle watchdog is the fallback)
# Usage (server): deploy/experiments/full_run.sh   (or give VRPQ_PROVERS/VRPQ_PROVER_KEY of running provers)
#   TIER=scale: the same run at the scale tier (code-path check: no tables/figures)
#   RESUME=1: skip step 1 (no provers), e.g. to finish a run stopped by its hard cap
set -uo pipefail
cd "$(dirname "$0")/../.."
TIER=${TIER:-experiment}
echo "full run ($TIER) start $(date -u +%FT%TZ)"
# step 1: VeRedact-PQ's Exp. 1 systems (VRPQ_EXP1) with remote prover hosts. Given (VRPQ_PROVERS) or launched here with the
# instance's IAM role and terminated right after; if they cannot be launched, the step is SKIPPED (no silent
# fallback to the load-generator-bound local mode) and the coverage check below reports the missing points.
VRPQ_EXP1=veredact,veredact-per-request,veredact-fixed-batch,veredact-cora-no-sfmr  # every system that proves
LAUNCHED=0
if [[ "${RESUME:-0}" == 1 ]]; then
  echo "STEP1: skipped (RESUME=1)"
elif [[ -z "${VRPQ_PROVERS:-}" ]]; then
  # PROVER_COUNT (open, HANDOFF D1): one c7i.48xlarge is 192 cores against ~150 core-s/s at 5,000 req/s, so 1 may
  # be enough (~US$20 instead of ~US$40 for the ~1.7 h they are up). Whichever is chosen must stay the same for
  # EVERY point: the published latency runs arrival -> finalized, so the wait for a free prover is inside p95.
  # Prover-bound shows as submitted_on_time falling while decided/offered stays high.
  if deploy/server/provision_provers_local.sh "${PROVER_COUNT:-2}" "${PROVER_TYPE:-c7i.48xlarge}"; then
    export VRPQ_PROVER_KEY=$(sed -n 1p deploy/aws/.provers) VRPQ_PROVERS=$(sed -n 2p deploy/aws/.provers)
    LAUNCHED=1
  else
    echo "STEP1: prover hosts could not be launched - VeRedact-PQ's Exp. 1 is NOT run (see coverage gaps)"
    deploy/server/teardown_provers_local.sh
  fi
fi
if [[ "${RESUME:-0}" != 1 && -n "${VRPQ_PROVERS:-}" ]]; then
  SYSTEMS=$VRPQ_EXP1 deploy/experiments/run_experiments.sh "$TIER" exp01_redaction_throughput
  echo "STEP1_EXIT=$?"
fi
(( LAUNCHED )) && deploy/server/teardown_provers_local.sh   # they also self-terminate 15 min after use
unset VRPQ_PROVERS VRPQ_PROVER_KEY
# step 2 never runs VeRedact-PQ's Exp. 1 systems: step 1 owns them (done with provers, or deliberately missing)
VRPQ_SKIP=$(sed 's/[^,]*/exp01_redaction_throughput:&/g' <<< "$VRPQ_EXP1") deploy/experiments/run_experiments.sh "$TIER" all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier "$TIER"
echo "COV_EXIT=$?"
if [[ "$TIER" == experiment ]]; then
  .venv/bin/python scripts/make_tables.py --tier experiment; echo "TABLES_EXIT=$?"
  .venv/bin/python scripts/make_figures.py --tier experiment; echo "FIGURES_EXIT=$?"
fi
echo "full run end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-full-run-done
