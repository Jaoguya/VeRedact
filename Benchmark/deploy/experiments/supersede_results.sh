#!/usr/bin/env bash
# Move every result folder of a tier (TIER, default experiment: experiment/, experiment-repNN/, experiment-reps/) to
# results/_superseded_<date>_<why>/ before a new run, so no older folder is skipped as "finished" or fills a gap.
# Usage (here and on the server): [TIER=smoke] deploy/experiments/supersede_results.sh <why>
set -euo pipefail
cd "$(dirname "$0")/../.."
shopt -s nullglob
T=${TIER:-experiment}
S=results/_superseded_$(date +%Y%m%d)_${T}_${1:?usage: $0 <why>}
n=0
for d in results/exp*/*/"$T" results/exp*/*/"$T"-rep[0-9][0-9] results/exp*/*/"$T"-reps; do
  t=$S/${d#results/}; mkdir -p "${t%/*}"; mv "$d" "$t"; n=$((n + 1))
done
echo "$n folders -> $S"
