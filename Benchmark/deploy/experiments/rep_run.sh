#!/usr/bin/env bash
# One repetition of the full run on a WORKER server (deploy/aws/provision_workers.sh): every (experiment, system)
# of the experiment tier except VeRedact-PQ's Exp. 1 systems (four), which the coordinator runs for every repetition with the
# shared prover hosts (deploy/experiments/rep_exp1_veredact.sh). Results: results/<exp>/<method>/experiment-repNN/.
# Ends with DONE and powers the worker off (stop, not terminate: results stay on its disk until collected).
# <part> splits one repetition over three workers (~10 h each instead of ~18 h on one; each scheme's Exp. 3/4 history
# stays on one machine): a = Exp. 0, 1 (baselines), 2, 5 · b = Exp. 3/4 VeRedact-PQ + S1 · c = Exp. 3/4 S13 · all = one worker.
# <rep> = single: one run into results/.../experiment/ (rep 1's seed, no repetition folders).
#   setsid nohup deploy/experiments/rep_run.sh <rep|single> [a|b|c|all] > results/logs/rep_run.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
REP=${1:?usage: $0 <rep|single> [a|b|c|all]}
[[ $REP == single ]] || export VRPQ_REP=$REP
export SKIP_TABLES=1   # tables/figures come from collect_reps.sh once every part is in
PART=${2:-all}
export VRPQ_SKIP=exp01_redaction_throughput:veredact,exp01_redaction_throughput:veredact-per-request,exp01_redaction_throughput:veredact-fixed-batch,exp01_redaction_throughput:veredact-cora-no-sfmr
case "$PART" in
  a)   EXPS="exp00_primitives exp01_redaction_throughput exp02_authorization_latency exp05_blockchain_overhead" ;;
  b)   EXPS="exp03_audit_efficiency exp04_verification_time"; export SYSTEMS=veredact,veredact-shared-evidence,veredact-per-record,S1 ;;
  c)   EXPS="exp03_audit_efficiency exp04_verification_time"; export SYSTEMS=S13 ;;
  all) EXPS=all ;;
  *)   echo "unknown part $PART"; exit 1 ;;
esac
sudo shutdown -h +${REP_HARD_CAP_MIN:-$([[ $PART == all ]] && echo 1440 || echo 840)} veredact-rep-hard-cap   # a hung run never keeps the worker up
echo "rep $REP part $PART start $(date -u +%FT%TZ)"
deploy/experiments/run_experiments.sh experiment $EXPS
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment   # gaps of the other parts are expected here
echo "COV_EXIT=$?"
echo "rep $REP end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-rep-done
