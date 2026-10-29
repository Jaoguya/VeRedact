#!/usr/bin/env bash
# After a split run: copy every worker's results here (starting stopped workers), push them to veredact-bench
# (older folders there moved aside first), check coverage and draw figures + tables there (repeated runs: aggregate
# with scripts/aggregate_reps.py first, VRPQ_RESULTS_TIER=experiment-reps), then fetch Result/ and Overleaf/tables
# back. TIER=smoke: coverage + aggregation there only, nothing moved aside, no tables or figures.
# Then, separately: deploy/aws/teardown_workers.sh. Usage: [TIER=smoke] deploy/aws/collect_reps.sh <single|R>
set -euo pipefail
cd "$(dirname "$0")/../.."
R=${1:?usage: $0 <single|R>}; TIER=${TIER:-experiment}
# "***" (the folder and everything in it): macOS's openrsync ignores "dir/**" when it is the sender (2026-10-30)
SEL="$TIER-rep[0-9][0-9]/***"; [[ $R == single ]] && SEL="$TIER/***"
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$RUN_REGION")   # the workers; veredact-bench (remote.sh) stays in AWS_REGION
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
REGION=$RUN_REGION deploy/aws/refresh_ssh_rule.sh >/dev/null
while read -r r IID _; do
  state=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
  [[ "$state" == running ]] || { "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null; "${A[@]}" ec2 wait instance-running --instance-ids "$IID"; }
  IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  for _ in $(seq 1 60); do ssh -n -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "$AWS_SSH_USER@$IP" true 2>/dev/null && break; sleep 5; done
  rsync -azm -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" --include '*/' --include "$SEL" \
    --include 'logs/**' --exclude '*' "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/results/" "results/"
  echo "worker $r: results copied"
done < deploy/aws/.workers
COV="for r in \$(seq 1 $R); do VRPQ_REP=\$r .venv/bin/python scripts/check_coverage.py --tier $TIER; done"
[[ $R == single ]] && COV=".venv/bin/python scripts/check_coverage.py --tier $TIER"
FETCH=0 deploy/aws/remote.sh TIER=$TIER deploy/experiments/supersede_results.sh before_collect   # only this run's folders there
IP=$(cut -d' ' -f2 deploy/aws/.instance)
rsync -azm -e "ssh -i $KEY" --include '*/' --include "$SEL" --exclude '*' "results/" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/results/"
if [[ $TIER != experiment ]]; then   # a smoke: coverage and aggregation only; no tables, figures or paper
  AGG=""; [[ $R == single ]] || AGG=" && .venv/bin/python scripts/aggregate_reps.py --tier $TIER --reps $R"
  FETCH=0 deploy/aws/remote.sh "$COV$AGG"
  exit
fi
if [[ $R == single ]]; then
  FETCH=results deploy/aws/remote.sh "$COV; .venv/bin/python scripts/make_tables.py --tier experiment && \
    .venv/bin/python scripts/make_figures.py --tier experiment"
  exit
fi
FETCH=results deploy/aws/remote.sh "$COV; .venv/bin/python scripts/aggregate_reps.py --tier experiment --reps $R && \
  VRPQ_RESULTS_TIER=experiment-reps .venv/bin/python scripts/make_tables.py --tier experiment && \
  VRPQ_RESULTS_TIER=experiment-reps .venv/bin/python scripts/make_figures.py --tier experiment"
