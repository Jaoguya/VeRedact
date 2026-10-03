"""Print deployment settings as shell assignments:  eval "$(.venv/bin/python deploy/aws/aws_config.py)".

configs/aws.toml sections are flattened as SECTION_KEY (AWS_REGION, BESU_IMAGE, REPO_URL, ...). The Besu
network SHAPE (validators, block period, netem delay, RPC port) is NOT in aws.toml: it comes from the tier's
composed config (configs/base.yaml + configs/tiers/$TIER.yaml, ledger section), so the network the code
measures is the network the config describes — one source, no drift. TIER defaults to "experiment".
"""
import os
import shlex
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from veredact_bench.utils.config import load

root = Path(__file__).resolve().parents[2]
cfg = tomllib.loads((root / "configs" / "aws.toml").read_text())
for section, values in cfg.items():
    for key, value in values.items():
        print(f"{section.upper()}_{key.upper()}={shlex.quote(str(value))}")
led = load(os.environ.get("TIER", "experiment"))["ledger"]
for k, v in {"VALIDATORS": led["validators"], "BLOCK_PERIOD_S": led["block_period_s"],
             "NETEM_DELAY_MS": led["netem_delay_ms"], "RPC_PORT": urlparse(led["rpc_url"]).port}.items():
    print(f"BESU_{k}={shlex.quote(str(v))}")
print(f"LEDGER_BACKEND={shlex.quote(led['backend'])}")
print(f"REPO_ROOT={shlex.quote(str(root))}")
