import os

import numpy as np
import pytest

from veredact_bench.baselines import SPECS, make_baseline
from veredact_bench.crypto.classical_ch import ETCHClassicalCH
from veredact_bench.crypto.pqch import LinearThresholdCH
from veredact_bench.ds.merkle import MerkleTree, verify_multiproof, verify_proof
from veredact_bench.env import make_ledger
from veredact_bench.protocol.veredact import Rejection, VeRedactPQ
from veredact_bench.workload import ZipfTargets


def test_merkle_proofs_and_bimc():
    leaves = [os.urandom(32) for _ in range(37)]
    t = MerkleTree(leaves)
    for i in (0, 5, 36):
        assert verify_proof(t.root, leaves[i], i, t.proof(i))
    pos = [1, 2, 3, 30]
    ok, _ = verify_multiproof(t.root, {p: leaves[p] for p in pos}, t.multiproof(pos), len(t.levels) - 1)
    assert ok
    changes = {p: os.urandom(32) for p in pos}
    coalesced = MerkleTree(leaves)
    ops_bimc = coalesced.update(changes)
    independent = MerkleTree(leaves)
    ops_indep = independent.update_independent(changes)
    assert coalesced.root == independent.root
    assert ops_bimc < ops_indep  # shared paths computed once


def test_threshold_pqch_adapt_and_reshare():
    ch = LinearThresholdCH(dim=32)
    pk, td, T = ch.dkeygen(n=7, t=5)
    r = ch.sample_r()
    h = ch.hash(pk, b"root-1", r)
    shares = [ch.part_adapt(td[k], b"root-1", r, b"root-2") for k in (1, 3, 4, 6, 7)]
    r2 = ch.combine(shares, r)
    assert ch.hash(pk, b"root-2", r2) == h
    assert ch.hash(pk, b"root-2", ch.combine(shares[:4], r)) != h  # below threshold fails
    td2 = ch.reshare(td, 5, 10, 7)
    r3 = ch.combine([ch.part_adapt(td2[k], b"root-2", r2, b"root-3") for k in range(1, 8)], r2)
    assert ch.hash(pk, b"root-3", r3) == h
    assert np.array_equal(ch.adapt(T, b"root-1", r, b"root-2"), r2)


def test_etch_classical_threshold():
    ch = ETCHClassicalCH()
    y, x = ch.keygen()
    h, rw = ch.hash(y, b"m")
    assert ch.verify(y, h, b"m", rw)
    shares = ch.share(x, 5, 3)
    rw2 = ch.threshold_adapt({i: shares[i] for i in (1, 2, 5)}, h, b"m'")
    assert ch.verify(y, h, b"m'", rw2)


@pytest.fixture(scope="module")
def ledger():
    return make_ledger(1024, verbose=False)


def test_veredact_end_to_end(ledger):
    v = VeRedactPQ(ledger.clone())
    tg = ZipfTargets(v.L, 1.2, seed=1)
    tids = list(dict.fromkeys(tg.pick_many(40)))[:12]
    reqs = [v.make_request(i, tid, b"new-%d" % i) for i, tid in enumerate(tids)]
    bad = [v.make_request(0, tids[0], b"x", tamper=f) for f in ("sig", "zk", "policy", "stale")]
    bad.append(v.make_request(0, b"TX-NOPE", b"x"))
    vrs = [v.validate(r) for r in reqs]
    assert all(not isinstance(x, Rejection) for x in vrs)
    assert all(isinstance(v.validate(r), Rejection) for r in bad)
    auth = v.authorize(vrs)
    rrs = v.execute(auth)
    assert len(rrs) == len(tids)
    n_transitions = sum(o.get("transitions", 0) for o in v.L.chain.ops)
    assert n_transitions == len({v.L.txs[t].b for t in tids})  # one PQCH adaptation per affected batch
    v.index_records()
    res = v.verify_audit(v.audit(rrs), deep=True)
    assert all(res.values())
    rrs[0].v_b_new -= 1  # stale record
    res = v.verify_audit(v.audit(rrs))
    assert not res[rrs[0].RID] and all(ok for rid, ok in res.items() if rid != rrs[0].RID)


def test_state_bound_authorization(ledger):
    v = VeRedactPQ(ledger.clone())
    tid = next(iter(v.L.txs))
    first = v.validate(v.make_request(0, tid, b"a"))
    second = v.validate(v.make_request(1, tid, b"b"))
    v.execute(v.authorize([first]))
    assert v.authorize([second]) is None  # stale after v_b advanced


@pytest.mark.parametrize("key", list(SPECS))
def test_baselines_process(ledger, key):
    b = make_baseline(key, ledger.clone())
    tid = next(iter(b.L.txs))
    rr = b.process(b.make_request(0, tid, b"new"))
    assert rr is not None
    if SPECS[key].audit:
        assert all(b.verify_audit(b.audit([rr])).values())
