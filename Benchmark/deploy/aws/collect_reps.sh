#!/usr/bin/env bash
# After a repeated run: copy every worker's experiment-repNN results here (starting stopped workers), push them to
# the coordinator, aggregate there (scripts/aggregate_reps.py) and draw figures + tables from the aggregate
# (VRPQ_RESULTS_TIER=experiment-reps), then fetch Result/ and Overleaf/tables back. Terminating the workers is a
# separate, explicit step: deploy/aws/teardown_workers.sh. Usage: deploy/aws/collect_reps.sh <R|single>
# single: one split run (results/.../experiment/): no aggregation, figures + tables straight from it.
set -euo pipefail
cd "$(dirname "$0")/../.."
R=${1:?usage: $0 <reps|single>}
SEL='*-rep[0-9][0-9]/**'; [[ $R == single ]] && SEL='experiment/**'
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
deploy/aws/refresh_ssh_rule.sh >/dev/null
while read -r r IID _; do
  state=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
  [[ "$state" == running ]] || { "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null; "${A[@]}" ec2 wait instance-running --instance-ids "$IID"; }
  IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  for _ in $(seq 1 60); do ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "$AWS_SSH_USER@$IP" true 2>/dev/null && break; sleep 5; done
  rsync -azm -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" --include '*/' --include "$SEL" \
    --include 'logs/**' --exclude '*' "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/results/" "results/"
  echo "worker $r: results copied"
done < deploy/aws/.workers
# the coordinator holds VeRedact-PQ's Exp. 1 repetitions; give it every worker's repetitions and aggregate there
FETCH=0 deploy/aws/remote.sh true
IP=$(cut -d' ' -f2 deploy/aws/.instance)
rsync -azm -e "ssh -i $KEY" --include '*/' --include "$SEL" --exclude '*' "results/" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/results/"
if [[ $R == single ]]; then
  FETCH=results deploy/aws/remote.sh ".venv/bin/python scripts/check_coverage.py --tier experiment && \
    .venv/bin/python scripts/make_tables.py --tier experiment && .venv/bin/python scripts/make_figures.py --tier experiment"
  exit
fi
FETCH=results deploy/aws/remote.sh ".venv/bin/python scripts/aggregate_reps.py --tier experiment --reps $R && \
  VRPQ_RESULTS_TIER=experiment-reps .venv/bin/python scripts/make_tables.py --tier experiment && \
  VRPQ_RESULTS_TIER=experiment-reps .venv/bin/python scripts/make_figures.py --tier experiment"
