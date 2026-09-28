#!/usr/bin/env bash
# Start a detached experiment run on the provisioned server (deploy/aws/provision_ec2.sh first).
#   - syncs this working tree (SYNC=local, default) so the run uses exactly the code you see
#   - installs the idle watchdog (powers off [run].idle_shutdown_minutes after the run ends)
#   - runs deploy/experiments/run_experiments.sh <tier> <exps> under nohup; survives logout
# Costs money while the instance runs. Usage:
#   deploy/aws/launch_run.sh <smoke|pilot|experiment> [exp1 ... | all]
#   deploy/aws/fetch_results.sh     # later: copy results/ and plot/ back
set -euo pipefail
cd "$(dirname "$0")/../.."
TIER=${1:?usage: $0 <smoke|pilot|experiment> [exp1 ... | all]}; shift
EXPS=${*:-all}
CONFIG="config/$TIER.toml" benchmark/.venv/bin/python -m veredact_bench.validate_config "config/$TIER.toml"
eval "$(python3 deploy/aws/aws_config.py)"
[[ -f deploy/aws/.instance ]] || { echo "no instance: run deploy/aws/provision_ec2.sh"; exit 1; }
read -r IID IP < deploy/aws/.instance
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
state=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
if [[ "$state" != running ]]; then
  "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null
  "${A[@]}" ec2 wait instance-status-ok --instance-ids "$IID"
  IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  echo "$IID $IP" > deploy/aws/.instance
fi
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$AWS_SSH_USER@$IP")
if [[ "${SYNC:-local}" == local ]]; then
  rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
    --exclude .git --exclude .venv --exclude __pycache__ --exclude target --exclude '/results/*' --exclude '/plot/*' \
    --exclude deploy/aws/.instance --exclude deploy/besu/.network ./ "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/"
fi
"${SSH[@]}" "echo '* * * * * root $REPO_REMOTE_DIR/deploy/server/idle_watchdog.sh' | sudo tee /etc/cron.d/veredact-idle >/dev/null"
"${SSH[@]}" "cd $REPO_REMOTE_DIR && mkdir -p results/logs && nohup deploy/experiments/run_experiments.sh $TIER $EXPS > results/logs/launch_$TIER.out 2>&1 < /dev/null & echo started pid \$!"
echo "follow: ssh -i $KEY $AWS_SSH_USER@$IP tail -f $REPO_REMOTE_DIR/results/logs/launch_$TIER.out"
