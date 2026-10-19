#!/usr/bin/env bash
# Low-cost full-size pilot (tier "scale", 2026-10-18): no prover hosts (US$20/h). Checks what is new:
#   1. prover start-up fix: VeRedact-PQ Exp. 1 through the remote-prover path on loopback (first proof < 1 s)
#   2. Exp. 2-5 at the 10^6-transaction ledger, Exp. 3/4 up to n_Q = 10^5 (cost and peak memory per experiment)
# Exp. 0 and the baselines' Exp. 1 at 10^6 already passed (results/logs/pilot_scale_try1.out); powers off when done.
#   setsid nohup deploy/experiments/pilot_scale.sh > results/logs/pilot_scale.out 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.."
sudo shutdown -h +${PILOT_HARD_CAP_MIN:-720} veredact-pilot-hard-cap
echo "pilot start $(date -u +%FT%TZ)"
RATES="100 5000" deploy/experiments/validate_provers_loopback.sh; echo "LOOPBACK_EXIT=$?"   # prints "first submission"
VRPQ_SKIP=exp01_redaction_throughput:veredact deploy/experiments/run_experiments.sh scale \
  exp02_authorization_latency exp03_audit_efficiency exp04_verification_time exp05_gas_consumption
echo "RUN_EXIT=$?"
.venv/bin/python scripts/check_coverage.py --tier scale; echo "COV_EXIT=$?"
echo "pilot end $(date -u +%FT%TZ)"; echo DONE
sudo shutdown -h +2 veredact-pilot-done
