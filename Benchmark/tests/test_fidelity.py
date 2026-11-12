"""Fidelity (negative) tests: every system rejects what its paper says it rejects, accepts what its paper
cannot check, and its capability claims match its behaviour. Run through Scheme + registry only.
Other/docs/baselines/*.md list the same checks as each baseline's fidelity checklist."""

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


def test_veredact_stale_request_fails_freshleaf_not_a_flag(cfg, ds):
    """#5 redesign (Exp. 1 invalid workload): a stale request is proved honestly, but against a content commitment
    an earlier redaction replaced. Phase 3 rejects it in FreshLeaf (its own leaf no longer matches), exactly as a
    real stale request, and the harness does not send it back for re-proving (an injected fault)."""
    from veredact_bench.evaluation.common import revalidate
    from veredact_bench.methods.scheme import RedactionOutcome

    s = open_system(cfg, "veredact", ds)
    r = faulty(ds, "stale", 5)
    a = authorize(s, r, prepare(s, r))
    assert not a.ok and a.reason == "freshness:stale state"
    assert not revalidate(r, RedactionOutcome(r.seq, False, reason=a.reason))
    assert decide(s, ds.trace[5])  # the same target without the fault is valid
    s.teardown()


@pytest.mark.parametrize("key", ["S1", "S13", "S27", "S34"])
def test_baseline_executes_a_stale_request(cfg, ds, key):
    """#5: no baseline binds a request to the content commitment it expects to replace, so a stale request is
    authorized like a valid one. Exp. 1 counts it as an accepted invalid request, never as throughput."""
    s = open_system(cfg, key, ds)
    assert decide(s, faulty(ds, "stale", 6))
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


def test_s99_batch_authentication_and_no_redaction(cfg, ds):
    """S99 (LETA): a valid platoon passes Eq. 13, one forged vehicle signature fails the whole batch, absent
    targets are refused, and it synthesises no redaction or audit (its paper defines none)."""
    s = open_system(cfg, "S99", ds)
    caps = s.capabilities()
    assert caps.pq_security and not caps.distributed_auth and not caps.verifiable_auditing
    assert not decide(s, faulty(ds, "absent"))
    good = [authorize(s, r) for r in ds.trace[:5]]
    assert all(a.ok for a in good)
    ok, ms = s.authorize_batch(good)
    assert ok and ms > 0
    bad = good[:4] + [authorize(s, faulty(ds, "sig", 5))]
    assert bad[-1].ok  # the PL's identity check cannot see a forged signature
    assert not s.authorize_batch(bad)[0]  # Eq. 13 does
    with pytest.raises(NotSupported):
        s.redact(good)
    with pytest.raises(NotSupported):
        s.audit(AuditQuery(1))


def test_s1_one_redaction_per_block(cfg, ds):
    s = open_system(cfg, "S1", ds)
    counts = build_history(s, ds.trace, 1)
    blocks = {s.block_of[r.tid][0] for r in ds.trace}
    assert counts["redacted"] == len(blocks)  # Jia's chain: exactly one redaction per touched block
    s.teardown()


def test_veredact_store_faults_give_a_verdict_per_record_and_are_undone(cfg, ds):
    """#35 plumbing only (no detection rate asserted): forged_approval and forged_proof are injected into the
    auditor's evidence stores, every returned record still gets a verdict, the result names the records the fault
    reaches, and the genuine entries are back afterwards."""
    s = open_system(cfg, "veredact", ds)
    build_history(s, ds.trace, cfg["veredact"]["reference_batch"])
    s.index_records()
    n = 4
    for kind in ("forged_approval", "forged_proof"):
        res = s.audit(AuditQuery(n, deep=True, tamper={1: kind}))
        assert set(res.accepted) == set(range(n)) and all(isinstance(v, bool) for v in res.accepted.values())
        assert res.tampered[1] == kind and set(res.tampered.values()) == {kind}
        if kind == "forged_approval":  # a shared node: every returned record of the batch depends on it
            bid = s.p.records[1].BID
            assert set(res.tampered) == {i for i in range(n) if s.p.records[i].BID == bid}
        assert all(s.audit(AuditQuery(n, deep=True)).accepted.values()), kind
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


def test_veredact_real_substituted_and_stale_evidence_are_rejected_per_record(cfg):
    """#8 step 2 change 3: 'substituted' carries another record's genuine evidence, 'stale' replays a genuine
    earlier transition and checkpoint of the same batch (anchored, correctly signed). Only the context binding
    (h_i^PBRP in the RAI entry, chi(v)) can catch them; each is rejected, every other record still accepted."""
    big = build_dataset(cfg, n_requests=160, zipf_s=1.2)  # skewed: batches are redacted more than once
    s = open_system(cfg, "veredact", big)
    build_history(s, big.trace, 8)
    s.index_records()
    recs = s.p.records
    later = next(
        i for i, r in enumerate(recs[:40]) if any(o.pbrp["b"] == r.pbrp["b"] and o.v_b_new < r.v_b_new for o in recs)
    )
    n = max(later + 1, 4)
    assert all(s.audit(AuditQuery(n)).accepted.values())
    for kind, i in (("substituted", 1), ("stale", later)):
        r = s._tamper(recs[i], kind, None, {}, i)
        if kind == "stale":  # a real, older checkpoint of the same batch, not an edited number
            old = r.pbrp["cp"]
            assert r.pbrp["b"] == recs[i].pbrp["b"] and r.v_b_new < recs[i].v_b_new
            assert any(o.pbrp["cp"] is old for o in recs if o is not recs[i])
        else:  # a genuine evidence object of a different record
            assert r.pbrp["RID"] != recs[i].RID and any(
                o.pbrp is not recs[i].pbrp and o.pbrp["RID"] == r.pbrp["RID"] for o in recs
            )
        acc = s.audit(AuditQuery(n, tamper={i: kind})).accepted
        assert not acc[i], kind
        assert all(ok for j, ok in acc.items() if j != i), kind
    s.teardown()


def test_s13_per_block_variant_is_registered_on_s13s_history(cfg, ds):
    """S13-per-block (#8) is S13 with the paper's Query phase per block: made by the registry and, in Exp. 3/4,
    run on S13's own history (HISTORY_OF), never on a history of its own."""
    from veredact_bench.evaluation.experiments.exp03_audit_efficiency import HISTORY_OF

    s = make(cfg, "S13-per-block")
    assert s.key == "S13-per-block" and s.per_block
    assert HISTORY_OF["S13-per-block"] == "S13"
    s = make(cfg, "S13-fallback")  # #35: Audit, then Query per block on F
    assert s.key == "S13-fallback" and s.fallback and not s.per_block
    assert HISTORY_OF["S13-fallback"] == "S13"


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
    # P6: the old and the new state of every distinct transition, PQCH.Hash(MR_b, r_b) = PQCH.Hash(MR_b', r_b')
    assert all(acc.values()) and p.c.counts["T_CH"] - before == 2 * distinct <= 2 * len(resp.records)
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


def test_remote_prover_service_reproduces_the_requesters(cfg, ds, tmp_path):
    """Audit A4: a prover service rebuilds the point's requester state from the bundle (same registry root) and
    its proofs/signatures validate exactly like local ones; faults stay rejected."""
    import os
    import signal
    import socket
    import subprocess
    import sys
    import threading
    import time

    from veredact_bench.evaluation.provers import RemoteProvers
    from veredact_bench.utils.config import REPO_ROOT

    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    env = dict(os.environ, VRPQ_PROVER_KEY="test-key")
    svc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "scripts" / "prover_service.py"), "--port", str(port), "--workers", "2"],
        env=env,
        start_new_session=True,  # its worker processes share the group: all of them stop at the end
    )
    try:
        time.sleep(3)
        os.environ["VRPQ_PROVER_KEY"] = "test-key"
        s = open_system(cfg, "veredact", ds)
        remote = RemoteProvers([f"127.0.0.1:{port}"], s)
        for fault in ("", "sig", "zk"):
            r = faulty(ds, fault, seq=5)
            got, box = threading.Event(), {}

            def make(r=r, box=box):
                box["R"], job = s.prepare_begin(r)
                return job

            def cb(proof, sig, box=box, got=got):
                box["R"].proof, box["R"].sigma_R = proof, sig
                got.set()

            remote.submit(make, cb)
            assert got.wait(60)
            assert authorize(s, r, box["R"]).ok == (fault == "")
        remote.close()
        s.teardown()
    finally:
        # terminating the service alone left its 2 workers running (2026-10-28: they kept veredact-bench "busy" for
        # its idle watchdog, so it stayed up 36 h): end the whole process group
        os.killpg(svc.pid, signal.SIGTERM)
        svc.wait()


def test_s1_authorization_cost_does_not_grow_with_history(cfg, ds):
    """A8: S1's 'already redacted?' check is a full node's local set test, so authorizing after many redactions
    costs about the same as at the start (it was O(history) with a per-request non-membership witness)."""
    s = open_system(cfg, "S1", ds)
    fresh = [r for r in ds.trace if not r.fault]
    first = [authorize(s, r, None).crypto_ms for r in fresh[:5]]
    build_history(s, ds.trace, 1)
    assert s.redacted
    redacted_block = s.redacted[0][1]
    again = next(r for r in fresh if s.block_of[r.tid][0] == redacted_block)
    assert not authorize(s, again, None).ok  # one redaction per block still enforced
    done = {b for _, b in s.redacted}
    open_tx = [t for t in ds.transactions if s.block_of[t.tid][0] not in done][:5]
    later = [
        authorize(s, RedactionRequest(10_000 + k, t.owner, t.tid, b"new", 0.0), None).crypto_ms
        for k, t in enumerate(open_tx)
    ]
    assert later and max(later) < 10 * max(first) + 5.0
    s.teardown()


def test_s1_chain_is_built_once_and_each_point_redacts_its_own_copy(cfg, ds):
    """S1's chain is cached per process (setup at the full ledger); a redaction in one point must not leak into the
    next point's chain, and the one-redaction-per-block rule still holds inside a point."""
    from veredact_bench.methods.baselines.s01_improved_dch import adapter

    a = open_system(cfg, "S1", ds)
    r = ds.trace[0]
    assert a.redact([authorize(a, r)]).outcomes[0].ok
    assert not authorize(a, RedactionRequest(99_999, r.requester, r.tid, b"again", 0.0)).ok  # block taken
    b = open_system(cfg, "S1", ds)
    assert len(adapter._SETUP) == 1 and b.blocks[0] is not a.blocks[0]
    assert authorize(b, r).ok and b.redact([authorize(b, r)]).outcomes[0].ok  # pristine copy
    assert cfg["baselines"]["S1"]["txs_per_block"] == 1 and len(b.blocks) == len(ds.transactions)
    a.teardown(), b.teardown()
