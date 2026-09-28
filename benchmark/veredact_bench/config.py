"""Load one config tier (config/smoke.toml | pilot.toml | experiment.toml). Nothing here has defaults:
every value the harness uses comes from the file, and validate_config gates the file first."""
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    with open(p, "rb") as f:
        return tomllib.load(f)


def threshold(n: int) -> int:
    """t = floor(2n/3) + 1 (manuscript Exp. 2)."""
    return (2 * n) // 3 + 1
