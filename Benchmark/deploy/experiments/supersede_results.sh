#!/usr/bin/env bash
# Move every experiment-tier result folder (experiment/, experiment-repNN/) to results/_superseded_<date>_<why>/
# before a new full run, so no older folder is skipped as "finished" or fills a gap of the new run.
# Usage (here and on the server): deploy/experiments/supersede_results.sh <why>
set -euo pipefail
cd "$(dirname "$0")/../.."
shopt -s nullglob
S=results/_superseded_$(date +%Y%m%d)_${1:?usage: $0 <why>}
n=0
for d in results/exp*/*/experiment results/exp*/*/experiment-rep[0-9][0-9]; do
  t=$S/${d#results/}; mkdir -p "${t%/*}"; mv "$d" "$t"; n=$((n + 1))
done
echo "$n folders -> $S"
