"""Saved redaction histories (evaluation/history_cache.py), the shared history list (data/history.py) and the
auditor's chain reads (anchor.read), on the smoke configuration (in-process ledger; one test needs Besu)."""

import copy
import json
import os

import pytest

from veredact_bench.data.dataset import build_dataset
from veredact_bench.data.history import history_requests
from veredact_bench.evaluation import history_cache
from veredact_bench.evaluation.common import build_history, open_system
from veredact_bench.methods.scheme import AuditQuery
from veredact_bench.utils.config import load

SCHEMES = ("veredact", "S1", "S13")
NEED = 40


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    c = copy.deepcopy(load("smoke", "exp03_audit_efficiency"))
    c["dataset"]["base_transactions"] = 1024
    c["output"]["dir"] = str(tmp_path_factory.mktemp("results"))
    return c


@pytest.fixture(scope="module")
def ds(cfg):
    return build_dataset(cfg, n_requests=30)


def _history(cfg, ds, key):
    reqs, hid = history_requests(cfg, ds, NEED)
    s = open_system(cfg, key, ds)
    counts = build_history(s, reqs, 8 if key == "veredact" else 1) | {"history_id": hid}
    return s, counts, hid


def _audit(s, n=NEED, tamper=None):
    return s.audit(AuditQuery(n, tamper=tamper or {})).accepted


def test_history_list_is_deterministic_and_reaches_need_for_every_scheme(cfg, ds):
    a, ha = history_requests(cfg, ds, NEED)
    b, hb = history_requests(cfg, ds, NEED)
    assert ha == hb and [r.tid for r in a] == [r.tid for r in b]
    assert len({r.tid for r in a}) >= NEED  # distinct targets: S1 (one redaction per block) reaches need too
    for key in SCHEMES:
        s, counts, _ = _history(cfg, ds, key)
        assert counts["redacted"] >= NEED, (key, counts)
        s.teardown()


@pytest.mark.parametrize("key", SCHEMES)
def test_saved_history_round_trip_gives_the_same_audit(cfg, ds, key):
    s, counts, hid = _history(cfg, ds, key)
    history_cache.save(cfg, key, 1, hid, ds, NEED, s, counts)
    if hasattr(s, "index_records"):
        s.index_records()
    before = _audit(s)
    s.teardown()
    got = history_cache.load(cfg, key, 1, hid, ds, NEED)
    assert got is not None
    t, counts2 = got
    assert counts2["redacted"] == counts["redacted"] and counts2["history_id"] == hid
    if hasattr(t, "index_records"):
        t.index_records()  # S13 witnesses are rebuilt and re-timed after a load, never taken from the file
    assert _audit(t) == before and all(before.values())
    if key == "S13":
        assert t._wit and t.witness_calibration > 0
    t.teardown()


def test_saved_history_is_refused_when_anything_differs(cfg, ds):
    s, counts, hid = _history(cfg, ds, "S13")
    history_cache.save(cfg, "S13", 1, hid, ds, NEED, s, counts)
    s.teardown()
    d = history_cache._dir(cfg, hid, "S13", 1)
    meta = json.loads((d / "meta.json").read_text())
    (d / "meta.json").write_text(json.dumps(meta | {"code_digest": "older-code"}))
    assert history_cache.load(cfg, "S13", 1, hid, ds, NEED) is None  # other code: rebuilt, never reused
    (d / "meta.json").write_text(json.dumps(meta))
    other = copy.deepcopy(cfg)
    other["baselines"]["S13"]["l_bits"] = 128
    assert history_cache.load(other, "S13", 1, hid, ds, NEED) is None  # other parameters
    assert history_cache.load(cfg, "S13", 1, "another-list", ds, NEED) is None  # other history list


def test_veredact_auditor_reads_the_anchored_checkpoints(cfg, ds):
    s, _, _ = _history(cfg, ds, "veredact")
    s.index_records()
    assert all(_audit(s).values())
    a = s.anchor
    e = s.p.rai_checkpoint[0]
    good = a._rai[e]
    a._rai[e] = b"\1" * 32  # the chain holds another CP_e^A: the response cannot be verified
    assert not any(_audit(s).values())
    a._rai[e] = good
    b, v = next(iter(k for k in a._cps if k[1] > 0))
    mr = a._cps[(b, v)]
    a._cps[(b, v)] = b"\2" * 32  # another anchored MR_b' for one transition: its records are rejected
    acc = _audit(s)
    assert not all(acc.values()) and any(acc.values())
    a._cps[(b, v)] = mr
    s.teardown()


def test_s1_auditor_reads_the_anchored_accumulator_and_records(cfg, ds):
    s, _, _ = _history(cfg, ds, "S1")
    s.index_records()
    assert all(_audit(s).values())
    s.anchor._accs["latest"] = b"\3" * 32  # the chain's latest header carries another acc
    assert not any(_audit(s).values())
    s.teardown()


@pytest.mark.skipif(not os.environ.get("VRPQ_BESU_KEY"), reason="needs a running Besu network")
def test_besu_checkpoint_read_from_anchoring_blocks_equals_full_scan(cfg):
    """On Besu: the anchoring-block read returns what a scan since deployment returns; audits still decide."""
    c = copy.deepcopy(cfg) | {"ledger": cfg["ledger"] | {"backend": "besu"}}
    d = build_dataset(c, n_requests=30)
    s, _, _ = _history(c, d, "veredact")
    s.index_records()
    a, keys = s.anchor, set(s.anchor.cp_block)
    full = {}
    for lo in range(a._from_block, a.w3.eth.block_number + 1, 5000):
        for e in a.reg.events.CheckpointAnchored.get_logs(from_block=lo, to_block=lo + 4999):
            full[(int(e.args.b), int(e.args.vb))] = bytes(e.args.mr)
    assert any(v for _, v in keys) and a.read("checkpoint_history", keys=keys) == {k: full[k] for k in keys}
    assert all(_audit(s).values()) and not all(_audit(s, tamper={0: "modified"}).values())
    s.teardown()
