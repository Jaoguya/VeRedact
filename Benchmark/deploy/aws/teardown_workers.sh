#!/usr/bin/env bash
# Terminate the split-run workers (instances tagged veredact-rep-worker / veredact-image-builder ONLY), any provers
# left in the run region, and the run's prebuilt image. Run after collect_reps.sh. Usage: [TIER=smoke] $0
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(.venv/bin/python deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$RUN_REGION")
IIDS=$("${A[@]}" ec2 describe-instances --filters "Name=tag:Name,Values=veredact-rep-worker,veredact-image-builder" \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId' --output text)
if [[ -n "$IIDS" ]]; then
  # persistent spot requests first, or they relaunch the terminated workers
  SIRS=$("${A[@]}" ec2 describe-instances --instance-ids $IIDS --query 'Reservations[].Instances[].SpotInstanceRequestId' --output text)
  if [[ -n "$SIRS" && "$SIRS" != None ]]; then "${A[@]}" ec2 cancel-spot-instance-requests --spot-instance-request-ids $SIRS >/dev/null; fi
  "${A[@]}" ec2 terminate-instances --instance-ids $IIDS >/dev/null
  echo "terminated: $IIDS"
else
  echo "no veredact-rep-worker instances"
fi
REGION=$RUN_REGION deploy/aws/teardown_provers.sh   # normally gone already (they stop themselves after use)
# the prebuilt image (build_image.sh) and its snapshot go after the full run; a smoke keeps them for it (TIER=smoke)
read -r IREG IMG SNAP _ < deploy/aws/.image 2>/dev/null || true
if [[ "${TIER:-experiment}" == experiment && "${KEEP_IMAGE:-0}" != 1 && "${IREG:-}" == "$RUN_REGION" && -n "${IMG:-}" ]]; then
  "${A[@]}" ec2 deregister-image --image-id "$IMG" && "${A[@]}" ec2 delete-snapshot --snapshot-id "$SNAP" && rm -f deploy/aws/.image
  echo "image $IMG and snapshot $SNAP deleted"
fi
