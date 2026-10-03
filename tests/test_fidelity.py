"""Fidelity (negative) tests: every system rejects what its paper says it rejects, accepts what its paper
cannot check, and its capability claims match its behaviour. Run through Scheme + registry only.
docs/baselines/*.md list the same checks as each baseline's fidelity checklist."""
import copy

import pytest

from veredact_bench.utils.config import load, load_all
from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import authorize, build_history, open_system, prepare
from veredact_bench.methods.registry import make
from veredact_bench.methods.scheme import AuditQuery, NotSupported, RedactionRequest

FAULTS = ("sig", "zk", "policy", "stale", "replay", "absent")


@pytest.fixture(scope="module")
def cfg():
    c = copy.deepcopy(load("smoke"))
    c["dataset"]["base_transactions"] = 1024  # test fixture size, not an experiment parameter
    return c


@pytest.fixture(scope="module")
def ds(cfg):
    return build_dataset(cfg, n_requests=40)


def faulty(ds, fault, seq=0):
    r = ds.trace[seq]
    return RedactionRequest(r.seq, r.requester, r.tid, r.new_payload, r.arrival_s, fault)


def decide(s, req):
    return authorize(s, req, prepare(s, req)).ok


def test_veredact_rejects_every_fault_class(cfg, ds):
    s = open_system(cfg, "veredact", ds)
    assert decide(s, ds.trace[0])  # a valid request passes (and becomes the replay source)
    for f in FAULTS:
        assert not decide(s, faulty(ds, f, 1)), f
    s.teardown()


@pytest.mark.parametrize("key", ["S1", "S13", "S27", "S34"])
def test_baseline_rejects_absent_target_and_claims_match(cfg, ds, key):
    s = open_system(cfg, key, ds)
    caps = s.capabilities()
    assert not decide(s, faulty(ds, "absent"))
    assert decide(s, ds.trace[0])
    # a system without policy control cannot reject a policy violation; one with it must
    assert decide(s, faulty(ds, "policy", 2)) != caps.policy_control
    # no baseline authenticates the request with a requester proof: zk faults pass everywhere
    assert decide(s, faulty(ds, "zk", 3))
    s.teardown()


@pytest.mark.parametrize("key", ["S27", "S34"])
def test_no_audit_protocol_is_not_synthesised(cfg, ds, key):
    s = open_system(cfg, key, ds)
    assert not s.capabilities().verifiable_auditing
    with pytest.raises(NotSupported):
        s.audit(AuditQuery(1))
    s.teardown()


def test_s1_one_redaction_per_block(cfg, ds):
    s = open_system(cfg, "S1", ds)
    counts = build_history(s, ds.trace, 1)
    blocks = {s.block_of[r.tid][0] for r in ds.trace}
    assert counts["redacted"] == len(blocks)  # Jia's chain: exactly one redaction per touched block
    s.teardown()


def test_audits_detect_tampering_with_their_own_granularity(cfg, ds):
    for key in ("veredact", "S1", "S13"):
        s = open_system(cfg, key, ds)
        build_history(s, ds.trace, cfg["veredact"]["fixed_batch"] if key == "veredact" else 1)
        if hasattr(s, "index_records"):
            s.index_records()
        n = 4
        clean = s.audit(AuditQuery(n))
        assert all(clean.accepted.values()), key
        bad = s.audit(AuditQuery(n, tamper={1: "modified"}))
        assert not bad.accepted[1], key
        if key == "S13":  # aggregate decision: the untampered records fall with it
            assert not any(bad.accepted.values())
        else:  # per-record decision
            assert all(ok for i, ok in bad.accepted.items() if i != 1), key
        s.teardown()


def test_registry_knows_every_configured_system(cfg):
    for exp, x in load_all("smoke")["experiments"].items():
        for key in x.get("systems", []) + [f"veredact:{v}" for v in x.get("variants", [])]:
            make(cfg, key)
