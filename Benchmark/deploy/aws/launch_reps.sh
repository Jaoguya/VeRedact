#!/usr/bin/env bash
# Start a repeated full run: the coordinator (veredact-bench) runs VeRedact-PQ's Exp. 1 for repetitions 1..R with
# the shared prover hosts; worker r (deploy/aws/.workers) runs everything else of repetition r. All detached;
# each server powers itself off when done. Later: deploy/aws/collect_reps.sh R, then deploy/aws/teardown_workers.sh.
# Usage: deploy/aws/launch_reps.sh <R>     (needs deploy/aws/provision_workers.sh R first)
set -euo pipefail
cd "$(dirname "$0")/../.."
R=${1:?usage: $0 <reps>}
[[ $(wc -l < deploy/aws/.workers) -eq $R ]] || { echo "deploy/aws/.workers must list $R workers"; exit 1; }
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
FETCH=0 deploy/aws/remote.sh "source ~/.cargo/env && .venv/bin/pip install -q -e '.[dev,server]' && mkdir -p results/logs && \
  (setsid nohup deploy/experiments/rep_exp1_veredact.sh $R > results/logs/rep_exp1.out 2>&1 < /dev/null &) && echo coordinator started"
while read -r r IID IP; do
  rr=$(printf %02d "$r")
  ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$AWS_SSH_USER@$IP" "cd $REPO_REMOTE_DIR/Benchmark && mkdir -p results/logs && \
    (setsid nohup deploy/experiments/rep_run.sh $r > results/logs/rep_run_r$rr.out 2>&1 < /dev/null &) && echo worker $r started"
done < deploy/aws/.workers
