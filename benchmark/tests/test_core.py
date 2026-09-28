"""Primitives, data structures, dataset determinism and config gating."""
import copy
import os

import pytest

from veredact_bench.config import CONFIG_DIR, load
from veredact_bench.crypto.pqch_sis import SISChameleonHash, default_params
from veredact_bench.dataset import build_dataset
from veredact_bench.ds.merkle import MerkleTree, verify_multiproof, verify_proof
from veredact_bench.validate_config import validate


@pytest.fixture(scope="module")
def cfg():
    return load("config/smoke.toml")


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
    from veredact_bench.crypto.pqzk_stark import PolicySTARK, ZKParams
    z = cfg["security"]["pqzk"]
    zk = PolicySTARK(ZKParams(z["queries"], z["blowup"], z["grinding_bits"], z["registry_depth"]), 4, seed=1)
    x = os.urandom(32)
    pi = zk.prove(1, x)
    assert zk.verify(1, x, pi)
    assert not zk.verify(2, x, pi)  # RequesterBound
    assert not zk.verify(1, os.urandom(32), pi)  # statement bound by Fiat-Shamir
    assert not zk.verify(1, x, zk.prove(1, x, secret_override=12345))  # unregistered credential


def test_dataset_is_deterministic_and_shared(cfg):
    a, b = build_dataset(cfg, n_requests=50), build_dataset(cfg, n_requests=50)
    assert a.dataset_id == b.dataset_id and [r.tid for r in a.trace] == [r.tid for r in b.trace]
    assert build_dataset(cfg, n_requests=50, seed_offset=1).dataset_id != a.dataset_id


@pytest.mark.parametrize("tier", ["smoke", "pilot", "experiment"])
def test_every_tier_validates(tier):
    err, _ = validate(CONFIG_DIR / f"{tier}.toml")
    assert err == []


def test_validator_rejects_weakened_baseline(tmp_path):
    src = (CONFIG_DIR / "experiment.toml").read_text()
    bad = tmp_path / "experiment.toml"
    bad.write_text(src.replace("rsa_bits = 3072                # [DERIVED] 128-bit classical (paper: RSA-1024)",
                               "rsa_bits = 1024"))
    err, _ = validate(bad)
    assert any("S34.rsa_bits" in e for e in err)
