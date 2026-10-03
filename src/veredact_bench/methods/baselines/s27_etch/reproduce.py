"""S27 [27] Liu et al. (ETCH) — reproduce the paper's evaluation with the original construction.

  Fig. 4 : KeyGen / Hash / Adapt / Verify time vs threshold t (secp256k1, SHA-256)
  Fig. 5 : per-hash overhead, ETCH vs SHA-256
  Fig. 6 : distributed redaction latency vs #redactors under RTT = 20/50/100/200/300 ms
           = measured compute + adapt_rounds x RTT (Adapt has 2 CA rounds; the paper's Fig. 6 values,
           < 0.38 s at 300 ms, imply ~1 RTT — set reproduction.adapt_rounds in configs/methods/s27_etch.yaml to compare)
  Not reproduced: Fig. 7 (chain growth) — the paper does not specify its update workload.
Output: results/S27_fig4_stages.csv, S27_fig5_hash.csv, S27_fig6_latency.csv
Usage:  python scripts/paper_reproduction.py s27_etch [--quick]
"""
import hashlib

from veredact_bench.methods.baselines.reproduce_common import Csv, cli, median_ms, scheme_config

from veredact_bench.methods.baselines.s27_etch.construction import Initiator, adapt, hash_, keygen, keyupt, verify, verify_tx, redact_tx


def fig4(ts, reps, keygen_reps):
    out = Csv("S27_fig4_stages")
    for t in ts:
        n = t
        keys = keygen(t, n)
        signers = list(keys.parts)[:t]
        v = hash_(keys.Y, b"tx")
        out.add(t=t, keygen_ms=median_ms(lambda: keygen(t, n), keygen_reps),
                hash_ms=median_ms(lambda: hash_(keys.Y, b"tx"), reps),
                adapt_ms=median_ms(lambda: adapt(keys, signers, v, b"tx'"), reps),
                verify_ms=median_ms(lambda: verify(keys.Y, b"tx", v), reps),
                keyupt_ms=median_ms(lambda: keyupt(keys), keygen_reps))
    out.save()


def fig5(reps, tx_bytes, sha256_reps):
    out = Csv("S27_fig5_hash")
    keys = keygen(3, 5)
    body = b"x" * tx_bytes
    e = median_ms(lambda: hash_(keys.Y, body), reps)
    s = median_ms(lambda: hashlib.sha256(body).digest(), sha256_reps)
    out.add(etch_ms=e, sha256_ms=s, ratio=e / s)
    out.save()


def fig6(redactors, rtts, reps, rounds):
    out = Csv("S27_fig6_latency")
    for t in redactors:
        keys = keygen(t, t)
        ini = Initiator()
        tx = ini.create_tx(keys.Y, b"tx")
        signers = list(keys.parts)[:t]
        comp = median_ms(lambda: redact_tx(keys, signers, tx, b"tx'"), reps)
        ok = verify_tx(keys.Y, ini.sk.public_key, redact_tx(keys, signers, tx, b"tx'"))
        for rtt in rtts:
            out.add(redactors=t, rtt_ms=rtt, rounds=rounds, compute_ms=comp, total_ms=comp + rounds * rtt,
                    redacted_tx_valid=ok)
    out.save()


if __name__ == "__main__":
    a = cli(__doc__)
    cfg = scheme_config("S27", a.quick)
    reps, ts, red = cfg["reps"], cfg["t_sweep"], cfg["redactors_sweep"]
    print("== S27 Fig. 4"); fig4(ts, reps, cfg["keygen_reps"])
    print("== S27 Fig. 5"); fig5(reps, cfg["fig5_tx_bytes"], cfg["fig5_sha256_reps"])
    print("== S27 Fig. 6"); fig6(red, cfg["rtt_ms"], reps, cfg["adapt_rounds"])
