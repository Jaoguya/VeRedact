"""S34 [34] J. Xue et al. (REBS) — reproduce the paper's evaluation with the paper's RSA-1024 instantiation.

  Fig. 3 : KeyGen (AttrKeyGen for the l required attributes) / Hash (CHash) / Verify (ChVer) /
           Adapt (Trap recovery + ChCld) / Update (TimeUpdate) time vs number of required attributes l
           (policy = l-of-l, the paper's "required attributes")
  Fig. 7 : communication: attribute keys + hash tuple (h, t, r) + ciphertext Info_Trap, in bits
Group: BLS12-381 (prime-order translation; paper used SS512 in Charm) — element sizes differ, so Fig. 7
values are ours, not the paper's (G1 48 B, G2 96 B, GT 576 B compressed).
Not reproduced: Fig. 3(e) Delegate (AVN join/leave is not built — docs/baselines/S34-rebs.md), Fig. 4
(needs [25]/[33] implementations), Figs. 5/6/8 (derived from the same measurements).
Output: results/S34_fig3_algorithms.csv, results/S34_fig7_communication.csv
Usage:  benchmark/.venv/bin/python experiment/S34_REBS/s34_run.py [--quick]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scheme_common import Csv, add_folder_to_path, cli, median_ms, scheme_config  # noqa: E402

add_folder_to_path(__file__)
import s34_scheme as R  # noqa: E402

G1_B, G2_B, GT_B = 48, 96, 576


def instance(bits, l):
    amc = R.gpgen(bits)
    avns = [R.key_avn() for _ in range(l)]
    pol = R.Policy(R.lsss_threshold(l, l), [R.rnd() for _ in range(l)], l)
    return amc, avns, pol


def fig3(cfg, reps):
    out = Csv("S34_fig3_algorithms")
    bits = cfg["rsa_bits"]
    for l in cfg["attributes_sweep"]:
        amc, avns, pol = instance(bits, l)
        k_tr, sig = R.key_tr(amc, b"TR")
        eph = R.rsa_key(bits)
        v, _, _ = R.chash(amc, avns, pol, b"tx", 1000, bits, eph)
        keys = {i: R.attr_keygen(amc, avns[i], b"TR", sig, pol.values[i]) for i in range(l)}
        trap = R.recover_trap(pol, v.info, b"TR", keys)
        out.add(l=l,
                keygen_ms=median_ms(lambda: [R.attr_keygen(amc, avns[i], b"TR", sig, pol.values[i]) for i in range(l)], reps),
                hash_ms=median_ms(lambda: R.chash(amc, avns, pol, b"tx", 1000, bits, eph), reps),
                hash_with_eph_rsa_keygen_ms=median_ms(lambda: R.chash(amc, avns, pol, b"tx", 1000, bits), reps),
                verify_ms=median_ms(lambda: R.chver(amc, b"tx", v), reps),
                adapt_ms=median_ms(lambda: R.chcld(amc, k_tr, R.recover_trap(pol, v.info, b"TR", keys), v, b"tx'"), reps),
                update_ms=median_ms(lambda: R.time_update(amc, k_tr, trap, v, b"tx", cfg["update_dt"]), reps))
    out.save()


def fig7(cfg):
    out = Csv("S34_fig7_communication")
    bits = cfg["rsa_bits"]
    for l in cfg["comm_attributes_sweep"]:
        amc, avns, pol = instance(bits, l)
        v, _, _ = R.chash(amc, avns, pol, b"tx", 1000, bits)
        mod_b = ((amc.n * v.n_tilde).bit_length() + 7) // 8
        keys_b = l * G1_B
        tuple_b = 2 * mod_b + (v.t.bit_length() + 7) // 8  # h, r in Z_{n n~}, t
        ct_b = len(v.info.c0) + l * (GT_B + 2 * G2_B) + len(v.info.h_trap)
        out.add(l=l, attribute_keys_bits=8 * keys_b, hash_tuple_bits=8 * tuple_b, ciphertext_bits=8 * ct_b,
                total_bits=8 * (keys_b + tuple_b + ct_b))
    out.save()


if __name__ == "__main__":
    a = cli(__doc__)
    cfg = scheme_config("S34", a.quick)
    print("== S34 Fig. 3"); fig3(cfg, cfg["reps"])
    print("== S34 Fig. 7"); fig7(cfg)
