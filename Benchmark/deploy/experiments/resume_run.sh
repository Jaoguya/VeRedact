#!/usr/bin/env bash
# Resume a full run stopped before its end (e.g. by its hard cap): steps 2-4 of full_run.sh only, NO prover hosts.
# Finished (experiment, system) points are skipped; VeRedact-PQ's Exp. 1 is never run here (step 1 owns it).
# Saved histories (results/_histories/) are loaded when their safeguards match, else rebuilt.
# Usage (server): HARD_CAP_MIN=360 nohup deploy/experiments/resume_run.sh > results/logs/resume_<date>.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
echo "resume start $(date -u +%FT%TZ)"
sudo shutdown -h "+${HARD_CAP_MIN:-360}" veredact-resume-hard-cap
VRPQ_SKIP=exp01_redaction_throughput:veredact deploy/experiments/run_experiments.sh experiment all
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier experiment
echo "COV_EXIT=$?"
.venv/bin/python scripts/make_tables.py --tier experiment; echo "TABLES_EXIT=$?"
.venv/bin/python scripts/make_figures.py --tier experiment; echo "FIGURES_EXIT=$?"
echo "resume end $(date -u +%FT%TZ)"
echo DONE
sudo shutdown -h +2 veredact-resume-done
