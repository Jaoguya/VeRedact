import os

import pytest

from veredact_bench.methods.baselines.s13_eaq_vrbc.construction import (
    Accumulator,
    Ledger,
    ch_verify,
    nonmem_aggregate,
    nonmem_create,
    nonmem_verify,
    nonmem_verify_agg,
    setup,
    tag_gen,
    tag_verify,
)


@pytest.fixture(scope="module")
def p():
    return setup(rsa_bits=1024, n_miners=3)


def test_tag_roundtrip(p):
    t, _, _ = tag_gen(p, 7, b"h7")
    assert tag_verify(p, 7, b"h7", t) and not tag_verify(p, 7, b"h8", t)


def test_redaction_keeps_chameleon_hash(p):
    L = Ledger(p)
    b = L.upload([b"a", b"b"])
    ch = b.ch
    assert L.redact(0, [b"a", b"B"])
    assert L.redact(0, [b"a", b"C"])  # redacting an already-redacted block uses the ephemeral trapdoor
    assert L.blocks[0].ch == ch and ch_verify(p, L.blocks[0])


def test_revoked_versions_fail_freshness(p):
    L = Ledger(p)
    for _i in range(6):
        L.upload([os.urandom(8)])
    _, _, hh_old = L.tags[2]
    L.redact(2, [b"new"])
    assert L.query_verify(2, L.query_prove(2))  # current version is fresh
    x_old = p.H1(2, hh_old)
    w = nonmem_create(L.acc, x_old)
    assert not nonmem_verify(L.acc, x_old, w)  # old version is revoked


def test_aggregated_nonmembership_and_audit(p):
    L = Ledger(p)
    for _i in range(12):
        L.upload([os.urandom(8)])
    for s in (0, 3):
        L.redact(s, [b"x%d" % s])
    chal = L.challenge(8)
    proof = L.audit_prove(chal)
    assert L.audit_verify(chal, proof)
    (V, S), mu, w = proof
    assert not L.audit_verify(chal, ((V, S), mu + 1, w))  # forged mu rejected
    A = Accumulator(p)
    xs = [p.H1(i, b"k") for i in range(5)]
    for x in xs[:2]:
        A.revoke(x)
    agg = nonmem_aggregate(A, [(x, nonmem_create(A, x)) for x in xs[2:]])
    th = A.theta()  # audit_prove passes the product once per audit: the witnesses must not change
    assert all(nonmem_create(A, x, th) == nonmem_create(A, x) for x in xs[2:])
    assert nonmem_verify_agg(A, agg)
