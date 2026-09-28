#!/usr/bin/env bash
# Stop (default) or terminate the experiment server so it stops costing money.
# Usage: deploy/aws/teardown_ec2.sh [stop|terminate]
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(python3 deploy/aws/aws_config.py)"
ACTION=${1:-stop}
IID=$(cut -d' ' -f1 deploy/aws/.instance)
case "$ACTION" in
  stop)      aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ec2 stop-instances --instance-ids "$IID" ;;
  terminate) read -r -p "Terminate $IID and delete its disk (results not fetched are lost)? [y/N] " a
             [[ "$a" == y ]] && aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ec2 terminate-instances --instance-ids "$IID" \
             && rm -f deploy/aws/.instance ;;
  *) echo "usage: $0 [stop|terminate]"; exit 1 ;;
esac
