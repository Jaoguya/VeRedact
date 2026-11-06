#!/usr/bin/env bash
# One-time repo setup, run by the repo admin (jaoguya) with the GitHub CLI: gh auth login, then bash .github/setup-repo.sh
set -euo pipefail
REPO=Jaoguya/VeRedact

label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force; }
label in-progress 0E8A16 "Someone (or their agent) is working on it"
label blocked     B60205 "Waiting on an answer; see the latest comment"
label needs-aws   FBCA04 "Needs jaoguya's yes (issue comment) before any AWS action"
label manuscript  5319E7 "Changes Overleaf/"
label baseline    C5DEF5 "Changes a baseline implementation"
for e in 1 2 3 4 5; do label "exp$e" 1D76DB "Experiment $e"; done

# main: PR required, 1 approval, code owners (AWS scripts -> jaoguya), CI job must pass.
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["test-lint"]},
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 1, "require_code_owner_reviews": true},
  "restrictions": null
}
JSON
echo "done: labels and branch protection on main"
