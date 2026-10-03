#!/usr/bin/env bash
# Copy results/ (raw runs) and paper/ (generated tables + figures) from the experiment server into this checkout.
# Usage: deploy/aws/fetch_results.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
IP=$(cut -d' ' -f2 deploy/aws/.instance)
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
for d in results paper; do
  rsync -avz -e "ssh -i $KEY" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/$d/" "$d/"
done
