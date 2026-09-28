"""System key -> Scheme instance. The ONLY place the runners learn which systems exist.

Keys match config [experiments.*].systems / variants:
  veredact                 VeRedact-PQ (ABRRR + BIMC)
  veredact:<variant>       internal variants (protocol/veredact_scheme.py VARIANTS)
  S1 S13 S27 S34           the four re-implemented baselines (experiment/S*/s*_baseline.py)

committee_n is the Exp. 2 sweep axis. Each system maps it to ITS OWN distribution parameter with
t = floor(2n/3)+1: VeRedact committee, S1 full nodes, S27 redactors, S34 attribute authorities
(l = n attributes, t-of-l policy). S13 has no distributed authorization and ignores it (recorded).
"""
import sys

from .config import REPO_ROOT, threshold
from .protocol.veredact_scheme import VARIANTS, VeRedactScheme

BASELINES = {
    "S1": ("S1_ImprovedDCH", "s1_baseline", "ImprovedDCHScheme"),
    "S13": ("S13_EAQVRBC", "s13_baseline", "EAQVRBCScheme"),
    "S27": ("S27_ETCH", "s27_baseline", "ETCHScheme"),
    "S34": ("S34_REBS", "s34_baseline", "REBSScheme"),
}


def _baseline_class(key: str):
    folder, module, cls = BASELINES[key]
    path = str(REPO_ROOT / "experiment" / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
    return getattr(__import__(module), cls)


def system_keys(cfg: dict, exp: str) -> list[str]:
    """systems + veredact variants of one experiment, in config order."""
    x = cfg["experiments"][exp]
    return list(x["systems"]) + [f"veredact:{v}" for v in x.get("variants", [])]


def make(cfg: dict, key: str, committee_n: int | None = None):
    t = threshold(committee_n) if committee_n else None
    if key == "veredact" or key.startswith("veredact:"):
        variant = key.split(":", 1)[1] if ":" in key else "veredact"
        if variant not in VARIANTS:
            raise KeyError(f"unknown VeRedact variant {variant}")
        return VeRedactScheme(cfg, variant, committee_n, t)
    cls = _baseline_class(key)
    if key == "S1":
        return cls(cfg, nodes_n=committee_n, threshold_t=t)
    if key == "S27":
        return cls(cfg, redactors_n=committee_n, threshold_t=t)
    if key == "S34":
        return cls(cfg, policy_attributes=committee_n, policy_threshold=t)
    return cls(cfg)


def distribution_param(key: str) -> str:
    return {"S1": "full nodes", "S27": "redactors", "S34": "policy attributes (AVN keys)",
            "S13": "none (single System Manager)"}.get(key.split(":")[0], "committee members")
