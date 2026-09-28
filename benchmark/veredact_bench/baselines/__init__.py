"""Re-implemented baselines, built from the repository-wide config/schemes.toml.

Manuscript methodology: 'all baselines were reimplemented within the same framework and instantiated
with the same PQ primitives ... each baseline otherwise follows its original workflow, including
per-request authorization and adaptation'. Each scheme entry in schemes.toml is one row of
manuscript Table IV (computation) / Table V (communication, on-chain state).
"""
import tomllib

from ..config import CONFIG_DIR
from .generic import BaselineSpec, PerRequestBaseline

with open(CONFIG_DIR / "schemes.toml", "rb") as _f:
    REGISTRY = tomllib.load(_f)["schemes"]

_FIELDS = ("classical_sig", "validate", "authorize", "adapt", "audit", "onchain", "grounded")

SPECS: dict[str, BaselineSpec] = {}
EXP_BASELINES: dict[int, list[str]] = {i: [] for i in range(1, 6)}
for sid, s in sorted(REGISTRY.items(), key=lambda kv: kv[1]["ref"]):
    if sid == "veredact":
        continue
    SPECS[s["key"]] = BaselineSpec(
        ref=s["ref"], label=s["label"], note=s.get("note", ""), scheme_id=sid,
        folder=s.get("folder", ""), **{k: (s[k] or None) if k == "audit" else s[k] for k in _FIELDS})
    for e in s["experiments"]:
        EXP_BASELINES[e].append(s["key"])


def make_baseline(key, ledger, pq_adapted=True):
    return PerRequestBaseline(SPECS[key], ledger, pq_adapted=pq_adapted)
