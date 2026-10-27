#!/usr/bin/env bash
# Terminate the repetition workers (instances tagged Name=veredact-rep-worker ONLY). Run after collect_reps.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
IIDS=$("${A[@]}" ec2 describe-instances --filters "Name=tag:Name,Values=veredact-rep-worker" \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId' --output text)
[[ -n "$IIDS" ]] || { echo "no veredact-rep-worker instances"; exit 0; }
# persistent spot requests first, or they relaunch the terminated workers
SIRS=$("${A[@]}" ec2 describe-instances --instance-ids $IIDS --query 'Reservations[].Instances[].SpotInstanceRequestId' --output text)
[[ -n "$SIRS" && "$SIRS" != None ]] && "${A[@]}" ec2 cancel-spot-instance-requests --spot-instance-request-ids $SIRS >/dev/null
"${A[@]}" ec2 terminate-instances --instance-ids $IIDS >/dev/null
echo "terminated: $IIDS"
