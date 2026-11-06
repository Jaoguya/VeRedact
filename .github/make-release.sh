#!/usr/bin/env bash
# Publish a full run's results as a GitHub release (CLAUDE.md "Results releases"). Run from the repo root on the
# machine that holds Benchmark/results/ (needs gh logged in, zip):
#   bash .github/make-release.sh run-2026-11-03 8c46d2e
set -euo pipefail
TAG=${1:?tag, e.g. run-2026-11-03}; COMMIT=$(git rev-parse "${2:?commit the release points at}")
RES=Benchmark/results; OUT=$(mktemp -d)
compgen -G "$RES/exp*/*/experiment-reps/metrics.json" >/dev/null || { echo "no $RES/*/*/experiment-reps here"; exit 1; }

pack() {  # pack <zip name> <find tests...>: files under results/, paths kept, smoke/pilot/_histories never match
  local name=$1; shift
  (cd "$RES" && find . "$@" -type f -print | zip -q "$OUT/$name" -@)
  echo "$name  $(du -h "$OUT/$name" | cut -f1)"
}
META=( \( -name metrics.json -o -name config_resolved.yaml -o -name run_info.json \) )
pack experiment-reps.zip -path './exp*/*/experiment-reps/*' "${META[@]}"
pack per-run.zip         -path './exp*/*/experiment-rep[0-9][0-9]/*' "${META[@]}"
pack rows.zip            -path './exp*/*/experiment-rep[0-9][0-9]/*' -name rows.csv
pack logs-summary.zip    -path './logs/*' \( -name 'rep_run_*.out' -o -name 'collect_*.out' \)

awk '/^## Results: full run/{f=1} /^Status and open work/{f=0} f' README.md > "$OUT/notes.md"
gh release create "$TAG" --repo Jaoguya/VeRedact --target "$COMMIT" --title "Full run ${TAG#run-}" \
  --notes-file "$OUT/notes.md" "$OUT"/*.zip
