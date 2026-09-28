#!/usr/bin/env bash
# Copy results/ and plot/ from the experiment server into this checkout.
# Usage: deploy/aws/fetch_results.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(python3 deploy/aws/aws_config.py)"
IP=$(cut -d' ' -f2 deploy/aws/.instance)
KEY="$HOME/.ssh/$AWS_KEY_NAME.pem"
for d in results plot; do
  rsync -avz -e "ssh -i $KEY" "$AWS_SSH_USER@$IP:$REPO_REMOTE_DIR/$d/" "$d/"
done
