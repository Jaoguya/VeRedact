"""Exp. 5 — blockchain gas (manuscript Fig. 7, Table VIII). Besu receipts ONLY.

Per system, target skew s and batch size b: requests_per_point valid requests are redacted in
authorization batches of b (baselines: per request — their papers have no batch, so b does not change
their transactions and they run once per s). Every anchoring transaction the system sent after setup is
read from the anchor's receipt log (anchor._Metered) — one row per on-chain transaction — plus VeRedact's
RAI checkpoint. With ledger.backend = in_process there are no receipts: gas is left empty and the run is
marked; validate-config refuses that backend in the experiment tier.
"""

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import build_history, capability_fields, open_system
from veredact_bench.methods.registry import system_keys


def run(cfg, out):
    x = cfg["experiment"]
    for key in system_keys(cfg):
        if not out.begin(key):
            continue
        if cfg["ledger"]["backend"] != "besu":
            out.note(f"{x['id']} ran on the in_process ledger: code path exercised, gas NOT measured")
        for zs in x["zipf_sweep"]:
            ds = build_dataset(cfg, n_requests=x["requests_per_point"], zipf_s=zs)
            out.dataset(ds.dataset_id)
            for b in x["batch_sizes"] if key.startswith("veredact") else [1]:
                s = open_system(cfg, key, ds)
                mark = len(s.anchor.receipts)
                counts = build_history(s, ds.trace, b)
                if hasattr(s, "index_records"):
                    s.index_records()
                s.teardown()  # waits for every pending receipt
                tx = s.anchor.receipts[mark:]
                total = sum(g for _, _, g in tx if g is not None)
                for op, ms, gas in tx:
                    out.row(
                        experiment=x["id"],
                        system=key,
                        zipf_s=zs,
                        batch_size=b,
                        op=op,
                        gas_used=gas if gas is not None else "",
                        ledger_ms=ms,
                        redactions=counts["redacted"],
                        onchain_tx=len(tx),
                        gas_per_redaction=total / counts["redacted"] if counts["redacted"] and gas is not None else "",
                        backend=cfg["ledger"]["backend"],
                        **capability_fields(s),
                    )
                out.log.info(f"  {key:28s} s={zs} b={b:<4} tx={len(tx):<5} redactions={counts['redacted']} gas={total}")
        out.end()
