# Running the experiments on AWS

Settings: `Benchmark/configs/aws.toml` (server, Besu image/key, S3, idle shutdown) and the tier's composed config (`Benchmark/configs/tiers/<tier>.yaml` on `Benchmark/configs/base.yaml`)
(everything measured, including the Besu network shape in `[ledger]`). No credentials in the repo: the
scripts use the AWS CLI profile in `Benchmark/configs/aws.toml`.

## 0. Credentials (once)

```bash
aws sts get-caller-identity --profile default   # must print the account id
```

Keys pasted into a chat must be rotated in IAM.

## 1. Provision (~15 min, starts billing)

```bash
DRY_RUN=1 Benchmark/deploy/aws/provision_ec2.sh    # print the AWS calls only
Benchmark/deploy/aws/provision_ec2.sh              # key pair, SSH-only SG, r7i.4xlarge Ubuntu 24.04, bootstrap
```

Bootstrap (`Benchmark/deploy/server/bootstrap_server.sh`): Docker, Python 3.12, liboqs 0.16.0 + liboqs-python,
Rust + maturin (builds `vrpq_stark`), web3/py-solc-x, `.venv` (pinned deps from `Benchmark/pyproject.toml`), then the test suite.

## 2. Run (detached; survives logout)

```bash
Benchmark/deploy/aws/launch_run.sh smoke           # plumbing check on the server (in-process ledger)
Benchmark/deploy/aws/launch_run.sh pilot           # Besu; resolve [CONFIRM] values from its variance and saturation
Benchmark/deploy/aws/launch_run.sh experiment      # paper numbers (refuses unless validate-config passes)
Benchmark/deploy/aws/launch_run.sh experiment exp02_authorization_latency exp05_gas_consumption   # a subset
```

The paper's full run is `Benchmark/deploy/experiments/full_run.sh` on the server (provers for VeRedact-PQ's
Exp. 1, then everything else, coverage, tables, figures); `RESUME=1` skips the prover step to finish a stopped run.

`launch_run.sh` points the SSH rule at this machine's current IP (`refresh_ssh_rule.sh`; a changed home
IP otherwise times out), syncs this working tree, bootstraps a fresh instance or rebuilds the package and
the STARK module on a bootstrapped one, installs the idle watchdog (power-off after
`[run].idle_shutdown_minutes` without an experiment or SSH session) and starts
`Benchmark/deploy/experiments/run_experiments.sh <tier> <exps>` under `nohup`. That script validates the config,
starts Besu when `ledger.backend = besu` (network shaped by `[ledger]`, `VRPQ_BESU_KEY` = the private
genesis dev key), runs `Benchmark/scripts/run_eval.py` (results in `Benchmark/results/<experiment>/<method>/<tier>/`; finished methods are
skipped, so a relaunch continues where a stopped run ended), writes `Overleaf/tables` and `Result/`,
syncs to `[run].s3_uri` when set, and stops Besu.

The experiment tier refuses to run with any ML-DSA backend other than liboqs, with the in-process
ledger, or with baselines below 128-bit security.

## 3. Fetch and stop paying

```bash
Benchmark/deploy/aws/fetch_results.sh              # rsync Benchmark/results/ (without saved histories) and Result/ back
Benchmark/deploy/aws/teardown_ec2.sh               # stop (disk kept)  |  teardown_ec2.sh terminate
```
