from veredact_bench.methods.baselines.s27_etch.construction import (
    Initiator,
    N,
    adapt,
    gmul,
    hash_,
    keygen,
    keyupt,
    lagrange,
    redact_tx,
    verify,
    verify_tx,
)


def test_dkg_hash_key_matches_trapdoor():
    k = keygen(3, 5)
    assert k.Y == gmul(k._x)
    lam = lagrange([1, 2, 4])
    assert sum(lam[i] * k.parts[i].s for i in (1, 2, 4)) % N == k._x


def test_threshold_adapt_and_keyupt():
    k = keygen(3, 5)
    v = hash_(k.Y, b"m")
    assert verify(k.Y, b"m", v)
    v2 = adapt(k, [2, 3, 5], v, b"m2")
    assert verify(k.Y, b"m2", v2) and v2.h == v.h
    Y_before, x_before = k.Y, k._x
    keyupt(k)  # shares change, trapdoor and hash key do not
    assert k.Y == Y_before
    lam = lagrange([1, 4, 5])
    assert sum(lam[i] * k.parts[i].s for i in (1, 4, 5)) % N == x_before
    assert verify(k.Y, b"m3", adapt(k, [1, 4, 5], v2, b"m3"))


def test_below_threshold_rejected_and_chain_signature_survives():
    k = keygen(3, 5)
    ini = Initiator()
    tx = ini.create_tx(k.Y, b"pay 10")
    try:
        adapt(k, [1, 2], tx.etch, b"x")
        raise AssertionError("t-1 redactors must fail")
    except ValueError:
        pass
    tx2 = redact_tx(k, [1, 2, 3], tx, b"pay 1")
    assert verify_tx(k.Y, ini.sk.public_key, tx2) and tx2.sig == tx.sig
