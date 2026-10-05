"""Fidelity (negative) tests: every system rejects what its paper says it rejects, accepts what its paper
cannot check, and its capability claims match its behaviour. Run through Scheme + registry only.
docs/baselines/*.md list the same checks as each baseline's fidelity checklist."""

import copy

import pytest

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import authorize, build_history, open_system, prepare
from veredact_bench.methods.registry import make
from veredact_bench.methods.scheme import AuditQuery, NotSupported, RedactionRequest
from veredact_bench.utils.config import load, load_all

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
        build_history(s, ds.trace, cfg["veredact"]["reference_batch"] if key == "veredact" else 1)
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


def test_s13_reused_audit_response_gives_the_same_decision(cfg, ds):
    """Exp. 4 verifies S13's response again instead of rebuilding it: same decisions, tampering still caught."""
    s = open_system(cfg, "S13", ds)
    build_history(s, ds.trace, 1)
    for tamper in ({}, {1: "modified"}):
        first = s.audit(AuditQuery(4, tamper=tamper, reuse_response=True))
        again = s.audit(AuditQuery(4, tamper=tamper, reuse_response=True))
        assert again.accepted == first.accepted and again.retrieval_ms == first.retrieval_ms
        assert all(first.accepted.values()) == (not tamper)
    s.teardown()


def test_s13_prebuilt_witnesses_give_the_identical_audit_response(cfg, ds):
    """Witnesses built once (index_records) must be exactly Alg. 1's output: same response as a fresh build."""
    s = open_system(cfg, "S13", ds)
    build_history(s, ds.trace, 1)
    s.index_records()
    blocks = sorted({b for _, b in s.redacted})
    chal = [(i, 1000 + i) for i in blocks]
    assert s._cached_witnesses(chal) is not None
    assert s.L.audit_prove(chal, s._cached_witnesses(chal)) == s.L.audit_prove(chal)
    res = s.audit(AuditQuery(4))
    assert all(res.accepted.values()) and res.retrieval_ms >= min(ms for _, _, ms in s._wit.values())
    s.teardown()


def test_registry_knows_every_configured_system(cfg):
    for _exp, x in load_all("smoke")["experiments"].items():
        for key in x.get("systems", []):
            make(cfg, key)


def test_s1_history_is_topped_up_to_the_largest_n_q(cfg, ds):
    """No n_Q point may be unreachable: S1 (one redaction per block) gets untimed uniform requests until its
    history holds `need` redactions."""
    from veredact_bench.evaluation.common import fill_history

    s = open_system(cfg, "S1", ds)
    counts = build_history(s, ds.trace, 1)
    need = counts["redacted"] + 20
    fill_history(s, ds, cfg, need, 1, counts)
    assert counts["redacted"] >= need and len(s.redacted) >= need
    s.teardown()


def test_s34_reused_setup_is_never_modified_by_a_redaction(cfg, ds):
    """Exp. 1 points share S34's keys and hashes; a redaction in one point must not change another's table."""
    a = open_system(cfg, "S34", ds)
    b = open_system(cfg, "S34", ds)  # second point: reuses the shared setup, builds nothing new
    assert a.ch is not b.ch and all(a.ch[t] is b.ch[t] for t in a.ch)
    build_history(a, ds.trace, 1)
    changed = [t for t in a.ch if a.ch[t] is not b.ch[t]]
    assert changed and all(b.ch[t] is open_system(cfg, "S34", ds).ch[t] for t in changed)
    a.teardown()
    b.teardown()


def test_veredact_state_check_once_per_transition_and_tamper_still_caught(cfg, ds):
    """A2: the PQCH state-transition check runs once per (batch, transition) in a response, not per record,
    and a record whose r_b' was altered is still rejected (its key differs, so it is checked separately)."""
    s = open_system(cfg, "veredact", ds)
    build_history(s, ds.trace, cfg["veredact"]["reference_batch"])
    s.index_records()
    p = s.p
    q, sig = p.make_query("authorization+state", 8)
    resp = p.audit(p.records[:8], q, sig)
    before = p.c.counts["T_CH"]
    acc = p.verify_audit(resp, q)
    distinct = len({(rr.pbrp["b"], rr.pbrp["MR_new"]) for rr in resp.records})
    assert all(acc.values()) and p.c.counts["T_CH"] - before == distinct <= len(resp.records)
    import copy as _copy

    bad = _copy.deepcopy(resp)
    bad.records[0].pbrp["r_new"] = bad.records[0].pbrp["r_new"] + 1
    acc2 = p.verify_audit(bad, q)  # same signed query, one record's r_b' altered
    assert not acc2[bad.records[0].RID]
    s.teardown()


def test_veredact_split_request_equals_one_piece_request(cfg, ds):
    """Audit A3: Exp. 1 builds R_i in the main process (live batch version) and proves/signs in a requester
    process. The split request must validate exactly like make_request's, faults included."""
    s = open_system(cfg, "veredact", ds)
    for fault in ("", "sig", "zk", "stale"):
        r = faulty(ds, fault, seq=3)
        R, job = s.prepare_begin(r)
        R.proof, R.sigma_R = s.p.requester_work(job)  # what a requester process runs (uncounted primitives)
        assert authorize(s, r, R).ok == (fault == "")
    s.teardown()
