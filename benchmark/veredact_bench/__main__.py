"""CLI. Every experiment is gated on validate-config; there is no way to run one on an invalid config.

    python -m veredact_bench run primitives|exp1 [exp2 ...|all] --config config/smoke.toml
    python -m veredact_bench capabilities            # capability matrix, generated from the code
"""
import argparse
import sys
import time
from pathlib import Path

from .config import REPO_ROOT, load
from .validate_config import validate


def cmd_run(a):
    from .experiments import ALL
    from .results import RunWriter

    path = Path(a.config) if Path(a.config).is_absolute() else REPO_ROOT / a.config
    err, warn = validate(path)
    for m in warn:
        print(f"warning {m}")
    if err:
        for m in err:
            print(f"ERROR   {m}")
        sys.exit("config invalid: refusing to run (python -m veredact_bench.validate_config)")
    cfg = load(a.config)
    from .crypto.pqsig import load_pqsig
    backend = load_pqsig().name
    if "sim" in backend.lower():
        sys.exit(f"signature backend '{backend}' is an HMAC stand-in: refusing to run experiments")
    if cfg["meta"]["tier"] == "experiment" and "liboqs" not in backend:
        sys.exit(f"experiment tier requires the liboqs ML-DSA-65 backend (manuscript's library), got '{backend}': "
                 "export VRPQ_SIG_BACKEND=oqs (deploy/server/bootstrap_server.sh installs liboqs)")
    print(f"signature backend: {backend}")
    names = list(ALL) if "all" in a.experiments else a.experiments
    for name in names:
        out = RunWriter(cfg, name, a.config)
        print(f"=== {name} tier={cfg['meta']['tier']} ledger={cfg['ledger']['backend']} -> {out.dir}", flush=True)
        t = time.time()
        try:
            ALL[name](cfg, out)
        finally:
            out.close()
        print(f"=== {name} done in {time.time() - t:.1f}s", flush=True)


def cmd_capabilities(a):
    import dataclasses

    from .registry import BASELINES, make
    cfg = load(a.config)
    keys = ["veredact", *BASELINES]
    fields = [f.name for f in dataclasses.fields(make(cfg, "veredact").capabilities())]
    print("| capability | " + " | ".join(keys) + " |")
    print("|:--|" + ":-:|" * len(keys))
    caps = {k: dataclasses.asdict(make(cfg, k).capabilities()) for k in keys}
    for f in fields:
        print(f"| {f} | " + " | ".join("✓" if caps[k][f] else "✗" for k in keys) + " |")


def main():
    ap = argparse.ArgumentParser(prog="veredact_bench", description="VeRedact-PQ evaluation harness")
    sub = ap.add_subparsers(required=True)
    r = sub.add_parser("run", help="run experiments (gated by validate-config)")
    r.add_argument("experiments", nargs="+", choices=["primitives", "exp1", "exp2", "exp3", "exp4", "exp5", "all"])
    r.add_argument("--config", default="config/smoke.toml")
    r.set_defaults(fn=cmd_run)
    c = sub.add_parser("capabilities", help="print the capability matrix generated from Scheme.capabilities()")
    c.add_argument("--config", default="config/smoke.toml")
    c.set_defaults(fn=cmd_capabilities)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
