#!/usr/bin/env bash
# One repetition of the full run on a WORKER server (deploy/aws/provision_workers.sh): every (experiment, system)
# of the experiment tier except VeRedact-PQ's Exp. 1, which the coordinator runs for every repetition with the
# shared prover hosts (deploy/experiments/rep_exp1_veredact.sh). Results: results/<exp>/<method>/experiment-repNN/.
# Ends with DONE and powers the worker off (stop, not terminate: results stay on its disk until collected).
#   setsid nohup deploy/experiments/rep_run.sh <rep> > results/logs/rep_run.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
export VRPQ_REP=${1:?usage: $0 <rep>} VRPQ_SKIP=exp01_redaction_throughput:veredact
sudo shutdown -h +${REP_HARD_CAP_MIN:-900} veredact-rep-hard-cap   # a hung run never keeps the worker up
echo "rep $VRPQ_REP start $(date -u +%FT%TZ)"
deploy/experiments/run_experiments.sh experiment all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment
echo "COV_EXIT=$?"
echo "rep $VRPQ_REP end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-rep-done
