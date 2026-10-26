#!/usr/bin/env bash
# Run a command on the experiment server (veredact-bench) instead of this laptop: nothing heavy runs locally.
#   deploy/aws/remote.sh make test            -> starts the instance if stopped, refreshes the SSH rule for this
#                                                IP, syncs Benchmark/ to <remote>/Benchmark, runs the command there,
#                                                and copies the generated Result/ (figures) and Overleaf/tables back
#                                                (FETCH=0 skips; FETCH=results also copies Benchmark/results/)
# --delete: files removed here are removed on the server too (excluded paths are kept).
# The idle watchdog powers the instance off 30 min after the last command (deploy/server/idle_watchdog.sh).
# Only acts on the instance in deploy/aws/.instance (this project's own server).
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py 2>/dev/null || python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
read -r IID _ < deploy/aws/.instance
state=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].State.Name' --output text)
if [[ "$state" != running ]]; then
  echo "starting $IID ($state)" >&2
  "${A[@]}" ec2 wait instance-stopped --instance-ids "$IID" 2>/dev/null || true
  "${A[@]}" ec2 start-instances --instance-ids "$IID" >/dev/null
  "${A[@]}" ec2 wait instance-running --instance-ids "$IID"
fi
IP=$("${A[@]}" ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IID $IP" > deploy/aws/.instance
deploy/aws/refresh_ssh_rule.sh >/dev/null
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 "$AWS_SSH_USER@$IP")
for _ in $(seq 1 60); do "${SSH[@]}" -o ConnectTimeout=3 -o BatchMode=yes true 2>/dev/null && break; sleep 3; done
"${SSH[@]}" "date +%s | sudo tee /var/tmp/veredact-last-busy >/dev/null"   # a fresh boot must not count as idle
"${SSH[@]}" "mkdir -p $REPO_REMOTE_DIR/Benchmark"
rsync -az --delete -e "ssh -i $KEY" --exclude .git --exclude .venv --exclude __pycache__ --exclude target \
  --exclude .ruff_cache --exclude .pytest_cache --exclude '/results/*' --exclude .cache --exclude deploy/aws/.instance \
  --exclude deploy/besu/.network ./ "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/"
rc=0
"${SSH[@]}" "cd $REPO_REMOTE_DIR/Benchmark && $*" || rc=$?
case "${FETCH:-paper}" in
  paper)   # mirror the GENERATED folders only (no stale files): figures and tables
           for d in Result/Pdf Result/Picture Overleaf/tables; do
             mkdir -p "../$d"
             "${SSH[@]}" "test -d $REPO_REMOTE_DIR/$d" && \
               rsync -az --delete -e "ssh -i $KEY" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/$d/" "../$d/"
           done ;;
  results) deploy/aws/fetch_results.sh ;;
esac
exit $rc
