"""Primitives, data structures, dataset determinism and config gating."""

import os

import numpy as np
import pytest

from veredact_bench.data.dataset import build_dataset
from veredact_bench.methods.veredact.crypto.pqch_sis import SISChameleonHash, default_params
from veredact_bench.methods.veredact.ds.merkle import MerkleTree, verify_multiproof, verify_proof
from veredact_bench.utils import validate as validate_module
from veredact_bench.utils.config import load, load_all
from veredact_bench.utils.validate import validate


@pytest.fixture(scope="module")
def cfg():
    return load("smoke")


def test_merkle_proofs_and_bimc():
    leaves = [os.urandom(32) for _ in range(37)]
    t = MerkleTree(leaves)
    for i in (0, 5, 36):
        assert verify_proof(t.root, leaves[i], i, t.proof(i))
    pos = [1, 2, 3, 30]
    ok, _ = verify_multiproof(t.root, {p: leaves[p] for p in pos}, t.multiproof(pos), len(t.levels) - 1)
    assert ok
    changes = {p: os.urandom(32) for p in pos}
    coalesced, independent = MerkleTree(leaves), MerkleTree(leaves)
    ops_bimc = coalesced.update(changes)
    ops_indep = independent.update_independent(changes)
    assert coalesced.root == independent.root
    assert ops_bimc < ops_indep  # shared paths computed once


def test_sis_pqch_distributed_adapt_and_reshare(cfg):
    s = cfg["security"]["pqch"]
    ch = SISChameleonHash(default_params(s["n"], s["k"], s["sigma_R"], s["sigma_g"]), seed=1)
    pk, shares = ch.dkeygen(7, 5)
    r = ch.sample_r()
    h = ch.hash(pk, b"m", r)
    pert, z = ch.begin_adapt(pk, b"m", r, b"m'")
    r2 = ch.combine(pert, z, [ch.part_adapt(shares[k], z) for k in (1, 3, 4, 6, 7)])
    assert ch.verify(pk, h, b"m'", r2) and not ch.verify(pk, h, b"m''", r2)
    pert, z = ch.begin_adapt(pk, b"m", r, b"x")
    few = ch.combine(pert, z, [ch.part_adapt(shares[k], z) for k in (1, 2, 3, 4)])  # t-1 shares
    assert not ch.verify(pk, h, b"x", few)
    new = ch.reshare(shares, 5, 10, 7)
    pert, z = ch.begin_adapt(pk, b"m", r, b"y")
    r3 = ch.combine(pert, z, [ch.part_adapt(new[k], z) for k in range(1, 8)])
    assert ch.verify(pk, h, b"y", r3)


def test_stark_rejects_wrong_witness_statement_requester(cfg):
    import time

    from veredact_bench.methods.veredact.crypto.pqzk_stark import PolicySTARK, ZKParams

    z = cfg["security"]["pqzk"]
    now = int(time.time())
    zk = PolicySTARK(
        ZKParams(z["queries"], z["blowup"], z["grinding_bits"], z["registry_depth"], z["attribute_levels"], 86400),
        4,
        seed=1,
        now_s=now,
    )
    x, thr, ts = os.urandom(32), 3, now + 10
    pi = zk.prove(1, x, thr, ts)
    assert zk.verify(1, x, pi, thr, ts)
    assert not zk.verify(2, x, pi, thr, ts)  # RequesterBound
    assert not zk.verify(1, os.urandom(32), pi, thr, ts)  # statement bound by Fiat-Shamir
    assert not zk.verify(1, x, pi, thr + 1, ts)  # proof bound to the policy threshold
    assert not zk.verify(1, x, pi, thr, ts + 1)  # ... and to the request time
    assert not zk.verify(1, x, zk.prove(1, x, thr, ts, secret_override=12345), thr, ts)  # unregistered credential
    assert zk.prove(1, x, thr, ts, attribute_override=thr - 1) == b""  # PrivatePolicy: attribute below threshold
    assert zk.prove(1, x, thr, now + 86400) == b""  # ValidCred: expired credential


def test_dataset_is_deterministic_and_shared(cfg):
    a, b = build_dataset(cfg, n_requests=50), build_dataset(cfg, n_requests=50)
    assert a.dataset_id == b.dataset_id and [r.tid for r in a.trace] == [r.tid for r in b.trace]
    assert build_dataset(cfg, n_requests=50, seed_offset=1).dataset_id != a.dataset_id


@pytest.mark.parametrize("tier", ["smoke", "pilot", "experiment"])
def test_every_tier_validates(tier):
    err, _ = validate(tier)
    assert err == []


def test_validator_rejects_weakened_baseline(monkeypatch):
    weak = load_all("experiment")
    weak["baselines"]["S34"]["rsa_bits"] = 1024
    monkeypatch.setattr(validate_module, "load_all", lambda tier: weak)
    err, _ = validate("experiment")
    assert any("S34.rsa_bits" in e for e in err)


def test_validator_rejects_unknown_tier_override(monkeypatch):
    monkeypatch.setattr(
        validate_module, "tier_overrides", lambda tier: {"meta": {"tier": tier}, "ledger": {"backnd": "besu"}}
    )
    err, _ = validate("smoke")
    assert any("ledger.backnd" in e for e in err)


def test_dkg_cache_is_transparent(tmp_path):
    from veredact_bench.methods.veredact.crypto import pqch_sis

    params = default_params(32, 8, 1.0, 3.0)  # small lattice: the property, not the size, is under test
    fresh = SISChameleonHash(params, seed=5, cache_dir=tmp_path)
    pk1, sh1 = fresh.dkeygen(7, 5)
    r_after_fresh = fresh.sample_r()
    pqch_sis._dkg_memo.clear()  # force the disk path
    cached = SISChameleonHash(params, seed=5, cache_dir=tmp_path)
    pk2, sh2 = cached.dkeygen(7, 5)
    assert np.array_equal(pk1.A2, pk2.A2) and all(np.array_equal(sh1[x].S, sh2[x].S) for x in sh1)
    assert np.array_equal(r_after_fresh, cached.sample_r())  # a cache hit does not shift the adaptation RNG
    assert not sh2[1].S.flags.writeable
    h = cached.hash(pk2, b"m", r_after_fresh)
    pert, z = cached.begin_adapt(pk2, b"m", r_after_fresh, b"m'")
    assert cached.verify(
        pk2, h, b"m'", cached.combine(pert, z, [cached.part_adapt(sh2[k], z) for k in (2, 3, 5, 6, 7)])
    )


def test_round_vectorised_adaptation_matches_protocol(cfg):
    s = cfg["security"]["pqch"]
    ch = SISChameleonHash(default_params(s["n"], s["k"], s["sigma_R"], s["sigma_g"]), seed=9)
    pk, shares = ch.dkeygen(7, 5)
    msgs, new = [b"a", b"b", b"c"], [b"a'", b"b'", b"c'"]
    R_old = np.stack([ch.sample_r() for _ in msgs], axis=1)
    chs = [ch.hash(pk, m, R_old[:, j]) for j, m in enumerate(msgs)]
    P, Z = ch.begin_adapt_many(pk, msgs, R_old, new)
    R_new = ch.combine_many(P, Z, [ch.part_adapt_many(shares[k], Z) for k in (1, 2, 4, 5, 7)])
    assert ch.verify_many(pk, chs, new, R_new) == [True] * 3
    assert all(ch.verify(pk, chs[j], new[j], R_new[:, j]) for j in range(3))  # single-item verify agrees
    assert ch.verify_many(pk, chs, msgs, R_new) == [False] * 3  # still binding to the new content
    few = ch.combine_many(P, Z, [ch.part_adapt_many(shares[k], Z) for k in (1, 2, 4, 5)])  # t-1 members
    assert ch.verify_many(pk, chs, new, few) == [False] * 3


def test_besu_block_watcher_resolves_pipelined_transactions():
    """Fake chain: a transaction mined BEFORE it is registered (race) and one mined after must both resolve."""
    import threading
    import time
    from types import SimpleNamespace

    from veredact_bench.evaluation.anchor import BesuAnchor, gather

    blocks = {}
    eth = SimpleNamespace(
        block_number=0,
        get_block=lambda n: SimpleNamespace(transactions=blocks[n]),
        get_transaction_receipt=lambda h: SimpleNamespace(status=1, gasUsed=21000 + h[0]),
    )
    a = object.__new__(BesuAnchor)
    a.w3, a.poll_s, a.timeout_s, a.receipts = SimpleNamespace(eth=eth), 0.005, 5, []
    a._pending, a._mined, a._plock, a._stop, a._last_block = {}, {}, threading.Lock(), threading.Event(), 0
    a._watcher = threading.Thread(target=a._watch, daemon=True)
    a._watcher.start()
    blocks[1] = [b"\x01" * 32]
    eth.block_number = 1  # tx 1 mined before registration
    time.sleep(0.05)
    f1 = a._register(b"\x01" * 32, time.perf_counter())
    f2 = a._register(b"\x02" * 32, time.perf_counter())
    blocks[2] = [b"\x02" * 32]
    eth.block_number = 2
    both = gather([f1, f2])
    assert f1.result(timeout=2)[1] == 21001 and f2.result(timeout=2)[1] == 21002
    assert both.result(timeout=2)[1] == 21001 + 21002
    a.close()
