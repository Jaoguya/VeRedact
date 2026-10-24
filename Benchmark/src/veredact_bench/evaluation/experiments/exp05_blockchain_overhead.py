"""Exp. 5 — permissioned-blockchain finalization overhead (VeRedact-optimize.tex Fig. 7, exp5_blockchain_overhead).

For each validator count (experiment.validators) and number of affected transaction batches |Omega_e|
(experiment.affected_batches), one authorization round redacts one transaction in each of |Omega_e| distinct
batches (CORA/SFMR: one checkpoint A_b' per affected batch), then the round's records are indexed in RAI.
Measured per round: the size of the submitted redaction-finalization transaction (Phase 5: the |Omega_e| updated
checkpoints and the SA-RLI state, committed atomically) and the time from its submission to QBFT finalization;
likewise for the RAI checkpoint anchoring CP_{e_A}^A (Phase 6). No gas: the PBN is permissioned.
Besu backend: the QBFT network is restarted with each validator count (deploy/besu/start_besu_network.sh,
VRPQ_VALIDATORS) and left at ledger.validators afterwards. In-process ledger (smoke): the count is recorded only
and the size is the anchored payload's length (no signed transaction exists).
"""

import os
import subprocess

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import open_system
from veredact_bench.methods.registry import system_keys
from veredact_bench.methods.scheme import RedactionRequest
from veredact_bench.utils.config import REPO_ROOT


def restart_besu(n: int) -> None:
    """A fresh n-validator QBFT network (same block period, netem delay and RPC port)."""
    env = os.environ | {"VRPQ_VALIDATORS": str(n)}
    subprocess.run(["bash", "deploy/besu/stop_besu_network.sh"], cwd=REPO_ROOT, check=False)
    subprocess.run(["bash", "deploy/besu/start_besu_network.sh"], cwd=REPO_ROOT, env=env, check=True)


def run(cfg, out):
    x = cfg["experiment"]
    besu = cfg["ledger"]["backend"] == "besu"
    ds = build_dataset(cfg, n_requests=1)
    try:
        for key in system_keys(cfg):
            if not out.begin(key):
                continue
            out.dataset(ds.dataset_id)
            for n_val in x["validators"]:
                if besu:
                    restart_besu(n_val)
                s = open_system(cfg, key, ds)
                batches = sorted(s.ledger.batches)
                seq, nxt = 0, 0
                for omega in x["affected_batches"]:
                    if omega > len(batches):
                        raise RuntimeError(f"|Omega_e|={omega} exceeds the ledger's {len(batches)} batches")
                    for sample in range(x["samples_per_point"]):
                        picked = [batches[(nxt + i) % len(batches)] for i in range(omega)]
                        nxt = (nxt + omega) % len(batches)  # fresh batches for the next round where possible
                        reqs = []
                        for b in picked:  # one transaction per affected batch
                            tid = s.ledger.batches[b].tids[sample % len(s.ledger.batches[b].tids)]
                            reqs.append(RedactionRequest(seq, seq % ds.requesters, tid, b"redacted", 0.0))
                            seq += 1
                        auths = [s.authorize(r) for r in reqs]
                        if not all(a.ok for a in auths):
                            raise RuntimeError(
                                f"{key}: Exp. 5 request rejected: {[a.reason for a in auths if not a.ok]}"
                            )
                        res = s.redact(auths)
                        if not all(o.ok for o in res.outcomes):
                            raise RuntimeError(f"{key}: Exp. 5 round not executed ({res.outcomes})")
                        fin = res.finality
                        fin_ms, _ = fin.result()
                        records = s.p.records[-omega:]
                        s.p.index_records(records)
                        rai = s.p.pending_anchor[-1]
                        rai_ms, _ = rai.result()
                        out.row(
                            experiment=x["id"],
                            system=key,
                            validators=n_val,
                            ledger=cfg["ledger"]["backend"],
                            affected_batches=omega,
                            sample=sample,
                            checkpoints=s.p.last_exec["batches"],
                            finalize_tx_bytes=getattr(fin, "tx_bytes", ""),
                            finalize_ms=fin_ms,
                            rai_tx_bytes=getattr(rai, "tx_bytes", ""),
                            rai_ms=rai_ms,
                        )
                    out.log.info(f"  {key:28s} validators={n_val} |Omega_e|={omega} x {x['samples_per_point']}")
                s.teardown()
            out.end()
    finally:
        if besu:
            restart_besu(cfg["ledger"]["validators"])  # later experiments run on the configured network
