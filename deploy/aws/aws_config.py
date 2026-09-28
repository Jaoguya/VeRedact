"""Print deployment settings as shell assignments: eval "$(python3 deploy/aws/aws_config.py)".

config/aws.toml sections are flattened as SECTION_KEY (AWS_REGION, BESU_IMAGE, REPO_URL, ...). The Besu
network SHAPE (validators, block period, netem delay, RPC URL) is NOT in aws.toml: it comes from the
experiment config tier ($CONFIG, default config/experiment.toml) [ledger], so the network the harness
measures is the network the config describes — one source, no drift.
"""
import os
import shlex
import tomllib
from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[2]
cfg = tomllib.loads((root / "config" / "aws.toml").read_text())
for section, values in cfg.items():
    for key, value in values.items():
        print(f"{section.upper()}_{key.upper()}={shlex.quote(str(value))}")
tier = Path(os.environ.get("CONFIG", "config/experiment.toml"))
led = tomllib.loads((tier if tier.is_absolute() else root / tier).read_text())["ledger"]
for k, v in {"VALIDATORS": led["validators"], "BLOCK_PERIOD_S": led["block_period_s"],
             "NETEM_DELAY_MS": led["netem_delay_ms"], "RPC_PORT": urlparse(led["rpc_url"]).port}.items():
    print(f"BESU_{k}={shlex.quote(str(v))}")
print(f"REPO_ROOT={shlex.quote(str(root))}")
