#!/usr/bin/env bash
# Terminate the requester prover hosts (instances tagged Name=veredact-prover ONLY) and forget their addresses.
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py 2>/dev/null || python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
IIDS=$("${A[@]}" ec2 describe-instances --filters "Name=tag:Name,Values=veredact-prover" \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId' --output text)
if [[ -n "$IIDS" ]]; then
  "${A[@]}" ec2 terminate-instances --instance-ids $IIDS >/dev/null
  "${A[@]}" ec2 wait instance-terminated --instance-ids $IIDS
  echo "terminated: $IIDS"
else
  echo "no veredact-prover instances"
fi
rm -f deploy/aws/.provers
