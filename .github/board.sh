#!/usr/bin/env bash
# Move an issue's card on the team board (https://github.com/users/Ppdfd/projects/1):
#   bash .github/board.sh <issue-number> "Todo" | "In progress" | "Blocked" | "Done"
# Adds the issue to the board first if it is not there. Needs once: gh auth refresh -s project
set -euo pipefail
N=${1:?issue number}; STATUS=${2:?status}
OWNER=Ppdfd; NUM=1; REPO=Jaoguya/VeRedact
PID=$(gh project view "$NUM" --owner "$OWNER" --format json --jq .id)
FID=$(gh project field-list "$NUM" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')
OID=$(gh project field-list "$NUM" --owner "$OWNER" --format json \
      --jq ".fields[] | select(.name==\"Status\") | .options[] | select(.name==\"$STATUS\") | .id")
[[ -n "$OID" ]] || { echo "unknown status '$STATUS' (Todo, In progress, Blocked, Done)"; exit 1; }
ITEM=$(gh project item-add "$NUM" --owner "$OWNER" --url "https://github.com/$REPO/issues/$N" --format json --jq .id)
gh project item-edit --id "$ITEM" --project-id "$PID" --field-id "$FID" --single-select-option-id "$OID" >/dev/null
echo "#$N -> $STATUS"
