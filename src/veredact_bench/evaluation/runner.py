"""Run experiments: validate the tier, seed, then each experiment's runner writes results/<exp>/<method>/<tier>/.

Gates (refuse to run, never warn and continue): an invalid config; the HMAC signature stand-in; any
ML-DSA backend other than liboqs in the experiment tier.
"""
import time

from veredact_bench.evaluation.experiments import RUNNERS
from veredact_bench.evaluation.results import RunWriter
from veredact_bench.methods.veredact.crypto.pqsig import load_pqsig
from veredact_bench.utils.config import experiments, load
from veredact_bench.utils.log import get_logger
from veredact_bench.utils.seed import set_seed
from veredact_bench.utils.validate import validate


class RefuseToRun(SystemExit):
    pass


def check(tier: str) -> None:
    log = get_logger()
    err, warn = validate(tier)
    for m in warn:
        log.warning(m)
    if err:
        for m in err:
            log.error(m)
        raise RefuseToRun(f"tier {tier!r}: config invalid, refusing to run (scripts/validate_config.py {tier})")
    backend = load_pqsig().name
    if "sim" in backend.lower():
        raise RefuseToRun(f"signature backend {backend!r} is an HMAC stand-in: refusing to run experiments")
    if tier == "experiment" and "liboqs" not in backend:
        raise RefuseToRun(f"experiment tier requires the liboqs ML-DSA-65 backend, got {backend!r}: export "
                          "VRPQ_SIG_BACKEND=oqs (deploy/server/bootstrap_server.sh installs liboqs)")
    log.info(f"signature backend: {backend}")


def run(tier: str, names: list[str], force: bool = False) -> None:
    log = get_logger()
    check(tier)
    for name in experiments() if names == ["all"] else names:
        cfg = load(tier, name)
        set_seed(cfg["meta"]["seed"])
        out = RunWriter(cfg, force=force)
        log.info(f"=== {name} tier={tier} ledger={cfg['ledger']['backend']}")
        t = time.time()
        try:
            RUNNERS[name](cfg, out)
        except BaseException:
            if out.method:  # unfinished method: no metrics.json, so the next run redoes it
                log.error(f"{name} {out.method}: aborted; its folder has no metrics.json and will be re-run")
            raise
        log.info(f"=== {name} done in {time.time() - t:.1f} s")
