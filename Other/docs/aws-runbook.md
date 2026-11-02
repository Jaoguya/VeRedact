# Running the experiments on AWS

Settings: `Benchmark/configs/aws.toml` (server, Besu image/key, S3, idle shutdown) and the tier's composed config (`Benchmark/configs/tiers/<tier>.yaml` on `Benchmark/configs/base.yaml`)
(everything measured, including the Besu network shape in `[ledger]`). No credentials in the repo: the
scripts use the AWS CLI profile in `Benchmark/configs/aws.toml`.

## 0. Credentials (once)

```bash
aws sts get-caller-identity --profile veredact   # must print the account id
```

Keys pasted into a chat must be rotated in IAM.

## 1. Provision (~15 min, starts billing)

```bash
DRY_RUN=1 Benchmark/deploy/aws/provision_ec2.sh    # print the AWS calls only
Benchmark/deploy/aws/provision_ec2.sh              # key pair, SSH-only SG, r7i.4xlarge Ubuntu 24.04, bootstrap
```

Bootstrap (`Benchmark/deploy/server/bootstrap_server.sh`): Docker, Python 3.12, liboqs 0.16.0 + liboqs-python,
Rust + maturin (builds `vrpq_stark`), web3/py-solc-x, `.venv` (pinned deps from `Benchmark/pyproject.toml`), then the test suite.

## 2. Tests and smoke on veredact-bench

```bash
Benchmark/deploy/aws/remote.sh make test lint    # starts the server if needed, syncs this tree, runs there
Benchmark/deploy/aws/remote.sh make smoke        # plumbing check only (numbers never used)
```

`remote.sh` points the SSH rule at this machine's current IP (`refresh_ssh_rule.sh`), syncs `Benchmark/`, runs the
command and copies `Result/` and `Overleaf/tables` back. The idle watchdog (installed by `provision_ec2.sh`) powers
the server off `[run].idle_shutdown_minutes` after the last command.

## 3. The paper's full run (split, us-east-2, on demand)

Fair by construction: every experiment's systems share one machine (`Benchmark/src/veredact_bench/utils/run_plan.py`).
Hybrid plan: Exp. 2–5 in 3 runs, Exp. 0 and 1 in run 1 only, 13 workers (`[run] worker_type`, m7i.4xlarge) and one
prover host (`[run] prover_pools`, c8g.48xlarge, arm64) for VeRedact-PQ's Exp. 1.

```bash
Benchmark/deploy/aws/build_image.sh              # image of the committed tree (workers start in ~3 min)
TIER=smoke Benchmark/deploy/aws/provision_workers.sh 13 && TIER=smoke Benchmark/deploy/aws/launch_reps.sh 3   # smoke
Benchmark/deploy/aws/provision_workers.sh 13     # the full run ("start full run")
Benchmark/deploy/aws/launch_reps.sh 3            # prover first, then every part, detached; each worker powers off
Benchmark/deploy/aws/collect_reps.sh 3           # results to veredact-bench: coverage, aggregate_reps.py, tables, figures
Benchmark/deploy/aws/teardown_workers.sh         # workers, provers, image
```

The laptop may sleep during a launch: workers and provers bootstrap detached on the host and the laptop only polls
with retries (`deploy/aws/remote_lib.sh`), so a sleep pauses the launch and it resumes on wake. Parts other than e1
start before the provers, and a worker stopped by its idle watchdog while waiting is started again. Keep the laptop
awake for the fastest launch (`caffeinate -is deploy/aws/launch_reps.sh 3`; with the lid closed it must be plugged in).

A failed part is rerun whole: `ONLY="<worker n>" FORCE=--force Benchmark/deploy/aws/launch_reps.sh 3`.
Each worker runs `Benchmark/deploy/experiments/rep_run.sh <run> <part>` → `run_experiments.sh` (validates the config,
starts Besu, runs `scripts/run_eval.py`, stops Besu). The experiment tier refuses any ML-DSA backend other than
liboqs, the in-process ledger, and baselines below 128-bit security.

## 4. Stop paying

```bash
Benchmark/deploy/aws/fetch_results.sh            # rsync veredact-bench's Benchmark/results/ and Result/ here
Benchmark/deploy/aws/teardown_ec2.sh             # stop veredact-bench (disk kept)  |  teardown_ec2.sh terminate
```
