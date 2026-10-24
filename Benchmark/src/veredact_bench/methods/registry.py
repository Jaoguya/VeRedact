"""System key -> Scheme instance. The ONLY place the runners learn which systems exist.

Keys match configs/experiments/*.yaml systems:
  veredact                 VeRedact-PQ (CORA + SFMR + SAVER)
  veredact-<variant>       an internal ablation variant (VeRedactPQ.VARIANTS, e.g. veredact-cora-no-sfmr)
  S1 S13 S27 S34           the four redactable-blockchain baselines (methods/baselines/<scheme>/adapter.py)
  S99                      LETA, the post-quantum batch-authentication baseline (Exp. 0 and Exp. 2 only)

committee_n is the Exp. 2 sweep axis. Each system maps it to ITS OWN distribution parameter with
t = floor(2n/3)+1: VeRedact committee, S1 full nodes, S27 redactors, S34 attribute authorities
(l = n attributes, t-of-l policy). S13 and S99 have no distributed authorization and ignore it (recorded).
"""

import importlib
import os

from veredact_bench.methods.veredact.protocol.veredact_scheme import VeRedactScheme
from veredact_bench.utils.config import threshold

BASELINES = {  # key -> (package under methods/baselines/, adapter class)
    "S1": ("s01_improved_dch", "ImprovedDCHScheme"),
    "S13": ("s13_eaq_vrbc", "EAQVRBCScheme"),
    "S27": ("s27_etch", "ETCHScheme"),
    "S34": ("s34_rebs", "REBSScheme"),
    "S99": ("s99_leta", "LETAScheme"),
}


def _baseline_class(key: str):
    package, cls = BASELINES[key]
    return getattr(importlib.import_module(f"veredact_bench.methods.baselines.{package}.adapter"), cls)


def system_keys(cfg: dict) -> list[str]:
    """Systems of the experiment being run (cfg["experiment"]), in config order; VRPQ_SYSTEMS="veredact,S1"
    (run_eval.py --systems) restricts a run to some of them, e.g. VeRedact-PQ's Exp. 1 while the paid
    prover hosts are up. It never adds a system and never changes a configured axis."""
    keys = list(cfg["experiment"]["systems"])
    only = [k for k in os.environ.get("VRPQ_SYSTEMS", "").split(",") if k]
    keys = [k for k in keys if k in only] if only else keys
    # VRPQ_SKIP="exp01_redaction_throughput:veredact,...": (experiment, system) pairs another step owns
    skip = {tuple(p.split(":", 1)) for p in os.environ.get("VRPQ_SKIP", "").split(",") if ":" in p}
    return [k for k in keys if (cfg["experiment"].get("id"), k) not in skip]


def make(cfg: dict, key: str, committee_n: int | None = None):
    t = threshold(committee_n) if committee_n else None
    if key == "veredact" or key.startswith("veredact-"):
        return VeRedactScheme(cfg, committee_n, t, variant=key.partition("-")[2] or "full")
    cls = _baseline_class(key)
    if key == "S1":
        return cls(cfg, nodes_n=committee_n, threshold_t=t)
    if key == "S27":
        return cls(cfg, redactors_n=committee_n, threshold_t=t)
    if key == "S34":
        return cls(cfg, policy_attributes=committee_n, policy_threshold=t)
    return cls(cfg)


def distribution_param(key: str) -> str:
    return {
        "S1": "full nodes",
        "S27": "redactors",
        "S34": "policy attributes (AVN keys)",
        "S13": "none (single System Manager)",
        "S99": "none (single TEC verifier)",
    }.get(key, "committee members")


def capability_matrix(cfg: dict) -> str:
    """Markdown capability matrix generated from Scheme.capabilities() of every method."""
    import dataclasses

    keys = ["veredact", *BASELINES]
    caps = {k: dataclasses.asdict(make(cfg, k).capabilities()) for k in keys}
    lines = ["| capability | " + " | ".join(keys) + " |", "|:--|" + ":-:|" * len(keys)]
    for f in caps["veredact"]:
        lines.append(f"| {f} | " + " | ".join("✓" if caps[k][f] else "✗" for k in keys) + " |")
    return "\n".join(lines)
