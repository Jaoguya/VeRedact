"""System key -> Scheme instance. The ONLY place the runners learn which systems exist.

Keys match config [experiments.*].systems / variants:
  veredact                 VeRedact-PQ (ABRRR + BIMC)
  veredact:<variant>       internal variants (protocol/veredact_scheme.py VARIANTS)
  S1 S13 S27 S34           the four re-implemented baselines (methods/baselines/<scheme>/adapter.py)

committee_n is the Exp. 2 sweep axis. Each system maps it to ITS OWN distribution parameter with
t = floor(2n/3)+1: VeRedact committee, S1 full nodes, S27 redactors, S34 attribute authorities
(l = n attributes, t-of-l policy). S13 has no distributed authorization and ignores it (recorded).
"""
import importlib

from veredact_bench.utils.config import threshold
from veredact_bench.methods.veredact.protocol.veredact_scheme import VARIANTS, VeRedactScheme

BASELINES = {  # key -> (package under methods/baselines/, adapter class)
    "S1": ("s01_improved_dch", "ImprovedDCHScheme"),
    "S13": ("s13_eaq_vrbc", "EAQVRBCScheme"),
    "S27": ("s27_etch", "ETCHScheme"),
    "S34": ("s34_rebs", "REBSScheme"),
}


def _baseline_class(key: str):
    package, cls = BASELINES[key]
    return getattr(importlib.import_module(f"veredact_bench.methods.baselines.{package}.adapter"), cls)


def system_keys(cfg: dict) -> list[str]:
    """systems + veredact variants of the experiment being run (cfg["experiment"]), in config order."""
    x = cfg["experiment"]
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


def capability_matrix(cfg: dict) -> str:
    """Markdown capability matrix generated from Scheme.capabilities() of every method."""
    import dataclasses

    keys = ["veredact", *BASELINES]
    caps = {k: dataclasses.asdict(make(cfg, k).capabilities()) for k in keys}
    lines = ["| capability | " + " | ".join(keys) + " |", "|:--|" + ":-:|" * len(keys)]
    for f in caps["veredact"]:
        lines.append(f"| {f} | " + " | ".join("✓" if caps[k][f] else "✗" for k in keys) + " |")
    return "\n".join(lines)
