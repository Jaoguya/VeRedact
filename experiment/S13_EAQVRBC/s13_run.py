"""S13 [13] Zhang et al. (EAQ-VRBC) — reproduce the paper's off-chain evaluation with the original construction.

  Figs. 4/5 : audit proof generation / verification vs #challenged blocks c
  Figs. 6/7 : query proof generation / verification vs index of the queried block
  Figs. 8/9 : upload / redact computation vs #transactions per block
  (on-chain gas, Fig. 3, is measured for VeRedact-PQ's baselines by benchmark/ exp5 on Besu)
Output: results/S13_audit.csv, S13_query.csv, S13_upload_redact.csv
Usage:  benchmark/.venv/bin/python experiment/S13_EAQVRBC/s13_run.py [--quick]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scheme_common import Csv, add_folder_to_path, cli, median_ms, scheme_config  # noqa: E402

add_folder_to_path(__file__)
from s13_scheme import Ledger, mht_root, redact_block, setup, upload_block  # noqa: E402


def build_ledger(p, n_blocks, txs_per_block, revoked):
    L = Ledger(p)
    for _ in range(n_blocks):
        L.upload([os.urandom(16) for _ in range(txs_per_block)])  # 16-byte data per block item (paper)
    for s in range(min(revoked, n_blocks)):  # prior redactions populate the revocation list
        L.redact(s, [os.urandom(16) for _ in range(txs_per_block)])
    return L


def audit(p, cfg, reps):
    out = Csv("S13_audit")
    cs = cfg["challenged"]
    L = build_ledger(p, max(cs), cfg["audit_txs_per_block"], cfg["revoked"])
    for c in cs:
        chal = L.challenge(c)
        proof = L.audit_prove(chal)
        out.add(c=c, prove_ms=median_ms(lambda: L.audit_prove(chal), reps),
                verify_ms=median_ms(lambda: L.audit_verify(chal, proof), reps), valid=L.audit_verify(chal, proof))
    out.save()


def query(p, cfg, reps):
    out = Csv("S13_query")
    idx = cfg["query_index"]
    L = build_ledger(p, max(idx) + 1, cfg["query_txs_per_block"], cfg["revoked"])
    for s in idx:
        proof = L.query_prove(s)
        out.add(index=s, prove_ms=median_ms(lambda: L.query_prove(s), reps),
                verify_ms=median_ms(lambda: L.query_verify(s, proof), reps), valid=L.query_verify(s, proof))
    out.save()


def upload_redact(p, cfg, reps):
    out = Csv("S13_upload_redact")
    sizes = cfg["txs_per_block"]
    for n in sizes:
        txs = [os.urandom(64) for _ in range(n)]
        L = Ledger(p)
        b = upload_block(p, 0, b"prev", txs)
        out.add(txs_per_block=n, upload_ms=median_ms(lambda: L.upload(txs), reps),
                redact_ms=median_ms(lambda: redact_block(p, b, txs[::-1]), reps),
                mht_hash_ops=mht_root(txs)[1])
    out.save()


if __name__ == "__main__":
    a = cli(__doc__)
    cfg = scheme_config("S13", a.quick)
    reps = cfg["reps"]
    p = setup(cfg["rsa_bits"], cfg["miners"], cfg["l_bits"])
    print("== S13 audit (Figs. 4/5)"); audit(p, cfg, reps)
    print("== S13 query (Figs. 6/7)"); query(p, cfg, reps)
    print("== S13 upload/redact (Figs. 8/9)"); upload_redact(p, cfg, reps)
