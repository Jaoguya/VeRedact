#!/usr/bin/env bash
# Make the security group allow SSH from THIS machine's current public IP only: add <ip>/32 if missing and
# revoke every other port-22 rule. Home/mobile IPs change; a stale rule makes SSH time out.
# Usage: deploy/aws/refresh_ssh_rule.sh      (called by provision_ec2.sh and launch_run.sh)
set -euo pipefail
cd "$(dirname "$0")/../.."
eval "$(python3 deploy/aws/aws_config.py)"
A=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")
CIDR="$AWS_SSH_CIDR"
[[ "$CIDR" == auto ]] && CIDR="$(curl -fsS https://checkip.amazonaws.com)/32"
SG=$("${A[@]}" ec2 describe-security-groups --filters "Name=group-name,Values=$AWS_NAME_TAG" \
       --query 'SecurityGroups[0].GroupId' --output text)
[[ -n "$SG" && "$SG" != None ]] || { echo "security group $AWS_NAME_TAG not found: run provision_ec2.sh"; exit 1; }
current=$("${A[@]}" ec2 describe-security-groups --group-ids "$SG" \
           --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].IpRanges[].CidrIp' --output text)
for c in $current; do
  [[ "$c" == "$CIDR" ]] || "${A[@]}" ec2 revoke-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$c" >/dev/null
done
[[ " $current " == *" $CIDR "* ]] || "${A[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$CIDR" >/dev/null
echo "SSH allowed from $CIDR only ($SG)"
