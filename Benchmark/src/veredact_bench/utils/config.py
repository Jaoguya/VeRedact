"""Config composition (OmegaConf). Nothing here has defaults: every value the code uses comes from configs/.

    cfg = load("smoke", "exp01_redaction_throughput")

composes, in order (later wins):
    configs/base.yaml
    configs/datasets/<meta.dataset>.yaml
    configs/methods/*.yaml                       (all methods: VeRedact-PQ + baselines)
    configs/experiments/<experiment>.yaml        (-> cfg["experiment"])
    configs/tiers/<tier>.yaml                    (scale overrides; its experiments.<id> block -> cfg["experiment"])

and returns a plain dict. The resolved dict is what every run saves as config_resolved.yaml.
"""

import os
from pathlib import Path

from omegaconf import OmegaConf

REPO_ROOT = Path(__file__).resolve().parents[3]  # Benchmark/src/veredact_bench/utils/config.py -> Benchmark/
PROJECT_ROOT = REPO_ROOT.parent  # the repository: Benchmark/, Overleaf/, Result/, Reference/, Other/
RESULT_DIR = PROJECT_ROOT / "Result"  # paper figures: Result/Pdf/<name>.pdf and Result/Picture/<name>.png
TABLE_DIR = PROJECT_ROOT / "Overleaf" / "tables"  # paper tables: Overleaf/tables/<name>.tex
CONFIG_DIR = REPO_ROOT / "configs"
TIERS = ("smoke", "pilot", "scale", "experiment")
REP_SEED_STRIDE = 1000  # repetition r runs with meta.seed + (r - 1) * 1000: rep 1 = the single-run seed


def rep() -> int | None:
    """Repetition index of this process (VRPQ_REP=1..R, set per server in a repeated run), or None."""
    r = os.environ.get("VRPQ_REP")
    return int(r) if r else None


def results_tier(tier: str) -> str:
    """Results folder name of a tier: <tier>-repNN inside a repetition, else the tier itself."""
    r = rep()
    return f"{tier}-rep{r:02d}" if r else tier


def experiments() -> list[str]:
    """Experiment ids in manuscript order (file names configs/experiments/expNN_<name>.yaml)."""
    return sorted(p.stem for p in (CONFIG_DIR / "experiments").glob("exp*.yaml"))


def _yaml(path: Path):
    return OmegaConf.load(path)


def _shared(tier: str):
    """base + dataset + methods, plus the tier file split into (general overrides, per-experiment overrides)."""
    if tier not in TIERS:
        raise KeyError(f"unknown tier {tier!r}; expected one of {TIERS}")
    base = _yaml(CONFIG_DIR / "base.yaml")
    tier_cfg = _yaml(CONFIG_DIR / "tiers" / f"{tier}.yaml")
    tier_exps = tier_cfg.pop("experiments", OmegaConf.create({}))
    dataset = OmegaConf.select(tier_cfg, "meta.dataset") or base.meta.dataset
    parts = [base, _yaml(CONFIG_DIR / "datasets" / f"{dataset}.yaml")]
    parts += [_yaml(p) for p in sorted((CONFIG_DIR / "methods").glob("*.yaml"))]
    return OmegaConf.merge(*parts), tier_cfg, tier_exps


def load(tier: str, experiment: str | None = None) -> dict:
    """Resolved config of one experiment on one tier (experiment=None: shared sections only)."""
    shared, tier_cfg, tier_exps = _shared(tier)
    parts = [shared]
    if experiment is not None:
        if experiment not in experiments():
            raise KeyError(f"unknown experiment {experiment!r}; expected one of {experiments()}")
        exp = _yaml(CONFIG_DIR / "experiments" / f"{experiment}.yaml")
        exp = OmegaConf.merge(exp, {"experiment": tier_exps.get(experiment, {})})
        parts.append(exp)
    parts.append(tier_cfg)
    cfg = OmegaConf.to_container(OmegaConf.merge(*parts), resolve=True, throw_on_missing=True)
    if (r := rep()) is not None:  # an independent repetition: its own seed (dataset, trace, committee, audits)
        if r < 1:
            raise ValueError("VRPQ_REP must be >= 1")
        cfg["meta"]["rep"] = r
        cfg["meta"]["seed"] += (r - 1) * REP_SEED_STRIDE
    return cfg


def load_all(tier: str) -> dict:
    """Shared sections + every experiment under cfg["experiments"][<id>] (for validation and listings)."""
    cfg = load(tier)
    cfg["experiments"] = {e: load(tier, e)["experiment"] for e in experiments()}
    return cfg


def tier_overrides(tier: str) -> dict:
    """The raw tier file (to check that every override names an existing key)."""
    return OmegaConf.to_container(_yaml(CONFIG_DIR / "tiers" / f"{tier}.yaml"), resolve=True)


def dump(cfg: dict, path: Path) -> None:
    path.write_text(OmegaConf.to_yaml(OmegaConf.create(cfg)))


def threshold(n: int) -> int:
    """t = floor(2n/3) + 1 (manuscript Exp. 2)."""
    return (2 * n) // 3 + 1


def exp1_rates(x: dict, key: str) -> list:
    """Exp. 1 arrival rates of one system: its low_rates (below its capacity) followed by the shared rates."""
    return sorted([*(x.get("low_rates") or {}).get(key, []), *x["rates"]])
