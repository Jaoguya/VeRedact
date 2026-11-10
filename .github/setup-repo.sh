#!/usr/bin/env bash
# One-time repo setup, run by the repo admin (jaoguya) with the GitHub CLI: gh auth login, then bash .github/setup-repo.sh
set -euo pipefail
REPO=Jaoguya/VeRedact

label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force; }
label blocked     B60205 "Waiting on an answer; see the latest comment"
label needs-aws   FBCA04 "Needs a yes (owner in chat, or a team member on the issue) before any AWS action"
label manuscript  5319E7 "Changes Overleaf/"
label baseline    C5DEF5 "Changes a baseline implementation"
for e in 1 2 3 4 5; do label "exp$e" 1D76DB "Experiment $e"; done

# main: changes only through a PR, CI job must pass; no review required (the author merges).
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["test-lint"]},
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 0, "require_code_owner_reviews": false},
  "restrictions": null
}
JSON
echo "done: labels and branch protection on main"
