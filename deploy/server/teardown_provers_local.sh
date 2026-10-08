#!/usr/bin/env bash
# Run ON veredact-bench: terminate the prover hosts it launched (IAM role: only Name=veredact-prover instances).
set -uo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
IDS=$(cat deploy/aws/.prover_ids 2>/dev/null)
[[ -n "$IDS" ]] && aws --region "$AWS_REGION" ec2 terminate-instances --instance-ids $IDS --query 'TerminatingInstances[].CurrentState.Name' --output text
rm -f deploy/aws/.provers deploy/aws/.prover_ids
