#!/usr/bin/env bash
# Copy Benchmark/results/ (raw runs), Result/ (figures) and Overleaf/tables/ from the experiment server here.
# Usage: deploy/aws/fetch_results.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
IP=$(cut -d' ' -f2 deploy/aws/.instance)
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
rsync -avz -e "ssh -i $KEY" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/Benchmark/results/" "results/"
for d in Result Overleaf/tables; do
  mkdir -p "../$d"
  rsync -avz -e "ssh -i $KEY" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/$d/" "../$d/"
done
