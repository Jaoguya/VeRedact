from veredact_bench.methods.baselines.s34_rebs import construction as R

BITS = 1024


def _setup(l=5, t=3):
    amc = R.gpgen(BITS)
    avns = [R.key_avn() for _ in range(l)]
    pol = R.Policy(R.lsss_threshold(l, t), [R.rnd() for _ in range(l)], t)
    return amc, avns, pol


def test_chash_chver_and_redaction_by_authorized_tr():
    amc, avns, pol = _setup()
    v, _, _ = R.chash(amc, avns, pol, b"tx", 1000, BITS)
    assert R.chver(amc, b"tx", v)
    k_tr, sig = R.key_tr(amc, b"TR1")
    keys = {l: R.attr_keygen(amc, avns[l], b"TR1", sig, pol.values[l]) for l in (0, 2, 4)}
    trap = R.recover_trap(pol, v.info, b"TR1", keys)
    assert trap is not None
    v2 = R.chcld(amc, k_tr, trap, v, b"tx-redacted")
    assert R.chver(amc, b"tx-redacted", v2) and v2.h == v.h


def test_below_threshold_or_wrong_values_cannot_recover_trap():
    amc, avns, pol = _setup()
    v, _, _ = R.chash(amc, avns, pol, b"tx", 1000, BITS)
    _, sig = R.key_tr(amc, b"TR1")
    two = {l: R.attr_keygen(amc, avns[l], b"TR1", sig, pol.values[l]) for l in (0, 1)}
    assert R.recover_trap(pol, v.info, b"TR1", two) is None  # t-1 attributes
    wrong = {l: R.attr_keygen(amc, avns[l], b"TR1", sig, pol.values[l] + 1) for l in (0, 1, 2)}
    assert R.recover_trap(pol, v.info, b"TR1", wrong) is None  # attribute VALUES do not satisfy


def test_forged_amc_signature_and_collusion_rejected():
    amc, avns, pol = _setup()
    _, sig = R.key_tr(amc, b"TR1")
    assert R.attr_keygen(amc, avns[0], b"TR2", sig, pol.values[0]) is None  # Sig_AMC bound to identity
    v, _, _ = R.chash(amc, avns, pol, b"tx", 1000, BITS)
    _, sig2 = R.key_tr(amc, b"TR2")
    mixed = {0: R.attr_keygen(amc, avns[0], b"TR1", sig, pol.values[0]),
             1: R.attr_keygen(amc, avns[1], b"TR2", sig2, pol.values[1]),
             2: R.attr_keygen(amc, avns[2], b"TR2", sig2, pol.values[2])}
    assert R.recover_trap(pol, v.info, b"TR2", mixed) is None  # keys of two TRs cannot be combined


def test_time_update_keeps_hash():
    amc, avns, pol = _setup()
    v, p_t, q_t = R.chash(amc, avns, pol, b"tx", 1000, BITS)
    k_tr, sig = R.key_tr(amc, b"TR1")
    keys = {l: R.attr_keygen(amc, avns[l], b"TR1", sig, pol.values[l]) for l in (1, 2, 3)}
    trap = R.recover_trap(pol, v.info, b"TR1", keys)
    v2 = R.time_update(amc, k_tr, trap, v, b"tx", 60)
    assert R.chver(amc, b"tx", v2) and v2.t == 1060
