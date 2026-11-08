"""VeRedact-PQ protocol behaviour at the four agreed seams (Overleaf/VeRedact-optimize.tex):
Phase 3 state binding (validate), CORA selection, SFMR execution (execute), SAVER audit (verify_audit)."""

import copy
import dataclasses

import pytest

from veredact_bench.data.dataset import build_dataset
from veredact_bench.evaluation.common import open_system
from veredact_bench.utils.config import load


@pytest.fixture(scope="module")
def cfg():
    c = copy.deepcopy(load("smoke"))
    c["dataset"]["base_transactions"] = 1024  # test fixture size, not an experiment parameter
    return c


@pytest.fixture(scope="module")
def ds(cfg):
    return build_dataset(cfg, n_requests=200)


def request_for(ds, s, batch, avoid=()):
    """A trace request whose target lies in transaction batch `batch` (and is not one of `avoid`)."""
    for r in ds.trace:
        if not r.fault and r.tid not in avoid and s.ledger.txs[r.tid].b == batch:
            return r
    raise LookupError(f"no trace request on batch {batch}")


def redact(s, req):
    a = s.authorize(req)
    assert a.ok, a.reason
    res = s.redact([a])
    assert res.outcomes[0].ok
    return res


# ---------------------------------------------------------------- Phase 3 state binding
def test_state_digest_changes_only_with_its_own_batch(cfg, ds):
    """h_i^st binds a validated request to its batch checkpoint: the same transaction gets the same digest while
    its batch is unchanged, a redaction in ANOTHER batch leaves it unchanged (no needless staleness), and a
    redaction in its own batch changes it."""
    s = open_system(cfg, "veredact", ds)
    first = ds.trace[0]
    home = s.ledger.txs[first.tid].b
    other = next(b for b in s.ledger.batches if b != home)

    def digest():
        a = s.authorize(dataclasses.replace(first, seq=first.seq))
        assert a.ok, a.reason
        return a.handle.h_st

    before = digest()
    assert digest() == before
    redact(s, request_for(ds, s, other))
    assert digest() == before
    redact(s, request_for(ds, s, home, avoid={first.tid}))
    assert digest() != before


# ---------------------------------------------------------------- CORA selector (Phase 4 Step 1)
def test_frontier_size_on_an_eight_leaf_tree():
    """|F_b(L)|: unaffected siblings needed to rebuild every path from the leaves L to MR_b (depth 3)."""
    from veredact_bench.methods.veredact.protocol.cora import frontier_size

    assert frontier_size({0}, 3) == 3
    assert frontier_size({0, 1}, 3) == 2
    assert frontier_size({0, 7}, 3) == 4
    assert frontier_size({0, 1, 2, 3}, 3) == 1


def cand(rid, b, pos, admitted=0.0):
    from veredact_bench.methods.veredact.protocol.cora import Candidate

    return Candidate(rid=rid, b=b, pos=pos, admitted=admitted)


def pick(queue, target, now=0.1, t_max=0.5):
    from veredact_bench.methods.veredact.protocol.cora import cora_select

    chosen = cora_select(queue, now=now, target=target, b_max=8, depth=3, t_max=t_max, w_ch=10.0, w_f=1.0)
    return [c.rid for c in chosen]


def test_cora_prefers_requests_in_a_shared_batch():
    queue = [
        cand(b"B", 1, 0),
        cand(b"A0", 0, 0),
        cand(b"C", 2, 0),
        cand(b"A1", 0, 1),
        cand(b"D", 3, 0),
        cand(b"A2", 0, 2),
    ]
    assert sorted(pick(queue, target=3)) == [b"A0", b"A1", b"A2"]


def test_cora_always_takes_requests_that_reached_the_waiting_bound():
    queue = [cand(b"A0", 0, 0), cand(b"A1", 0, 1), cand(b"A2", 0, 2), cand(b"OLD", 3, 5, admitted=-1.0)]
    chosen = pick(queue, target=3, now=0.0)
    assert b"OLD" in chosen and len(chosen) == 3


def test_cora_prefers_the_overlapping_path_inside_a_batch():
    """With pos 0 chosen, pos 1 shares its path (frontier 3 -> 2) while pos 7 does not (3 -> 4)."""
    queue = [cand(b"P0", 0, 0, admitted=-0.1), cand(b"P7", 0, 7), cand(b"P1", 0, 1)]
    assert pick(queue, target=2) == [b"P0", b"P1"]


# ---------------------------------------------------------------- SFMR execution (Phase 5)
def validated(s, req):
    a = s.authorize(req)
    assert a.ok, a.reason
    return a


def test_one_pqch_adaptation_per_affected_batch(cfg, ds):
    s = open_system(cfg, "veredact", ds)
    home, other = 0, 1
    r1 = request_for(ds, s, home)
    r2 = request_for(ds, s, home, avoid={r1.tid})
    r3 = request_for(ds, s, other)
    res = s.redact([validated(s, r) for r in (r1, r2, r3)])
    assert all(o.ok for o in res.outcomes)
    assert res.ch_adaptations == 2  # |Omega_e| = 2 batches, not 3 requests


def test_execution_outside_the_authorized_plan_is_withheld(cfg, ds):
    """P_b^exec must be a subset of the positions fixed by Gamma_e: a request whose position is changed after the
    committee signed is not executed, and its batch keeps its version (the transition is withheld)."""
    s = open_system(cfg, "veredact", ds)
    r1 = request_for(ds, s, 0)
    r2 = request_for(ds, s, 0, avoid={r1.tid})
    auths = [validated(s, r) for r in (r1, r2)]
    batch_auth, _ = s.authorize_batch(auths)
    v_before = s.ledger.batches[0].v
    moved = next(p for p in range(s.ledger.N) if p not in {m.pos for m in batch_auth.members})
    batch_auth.members[0] = dataclasses.replace(batch_auth.members[0], pos=moved)
    res = s.redact(auths, batch_auth)
    assert not any(o.ok for o in res.outcomes)
    assert s.ledger.batches[0].v == v_before


# ---------------------------------------------------------------- SAVER audit (Phase 6)
@pytest.fixture(scope="module")
def audited(cfg, ds):
    """A VeRedact-PQ instance with a small redaction history (rounds of 8) indexed in RAI."""
    from veredact_bench.evaluation.common import build_history

    s = open_system(cfg, "veredact", ds)
    build_history(s, ds.trace[:40], 8)
    s.index_records()
    return s


def audit(s, records, deep=frozenset()):
    Q, sigma = s.p.make_query("authorization+state", len(records))
    resp = s.p.audit(records, Q, sigma)
    return s.p.verify_audit(resp, Q, deep=deep), dict(s.p.last_nodes)


def test_saver_verifies_each_shared_dependency_once(audited):
    s = audited
    s.p.vcs.clear()
    recs = s.p.records[:24]
    accepted, nodes = audit(s, recs)
    assert all(accepted.values())
    assert nodes["auth"] == len({r.BID for r in recs}) < len(recs)
    assert nodes["trans"] == len({(r.b, r.v_b_new) for r in recs}) < len(recs)
    assert nodes["req"] == len(recs)


def test_saver_reuses_only_identical_contexts(audited):
    s = audited
    s.p.vcs.clear()
    recs = s.p.records[:16]
    audit(s, recs)
    accepted, nodes = audit(s, recs)  # same evidence, same contexts: shared nodes are reused
    assert all(accepted.values()) and nodes["auth"] == 0 and nodes["trans"] == 0
    bad = copy.copy(recs[3])
    bad.pbrp = dict(bad.pbrp, theta=b"\x00" * 32)  # transition evidence from another context
    accepted, nodes = audit(s, recs[:3] + [bad] + recs[4:])
    assert not accepted[bad.RID]
    assert all(ok for rid, ok in accepted.items() if rid != bad.RID)
    assert nodes["trans"] == 1  # only the changed context is verified afresh


def test_deep_escalation_only_for_chosen_requests(audited):
    s = audited
    recs = s.p.records[:10]
    chosen = frozenset(r.RID for r in recs[:2])
    accepted, nodes = audit(s, recs, deep=chosen)
    assert all(accepted.values()) and nodes["zk"] == 2


# ---------------------------------------------------------------- internal variants (ablations)
def test_cora_no_sfmr_adapts_once_per_request(cfg, ds):
    s = open_system(cfg, "veredact-cora-no-sfmr", ds)
    r1 = request_for(ds, s, 0)
    r2 = request_for(ds, s, 0, avoid={r1.tid})
    r3 = request_for(ds, s, 1)
    v0 = s.ledger.batches[0].v
    res = s.redact([validated(s, r) for r in (r1, r2, r3)])
    assert all(o.ok for o in res.outcomes)
    assert res.ch_adaptations == 3  # independent Merkle update + PQCH adaptation per redaction
    assert s.ledger.batches[0].v == v0 + 2


def test_re_zk_committee_reverifies_every_proof(cfg, ds):
    s = open_system(cfg, "veredact-re-zk", ds)
    auths = [validated(s, request_for(ds, s, b)) for b in (0, 1, 2)]
    before = s.crypto.counts["T_ZV"]
    batch_auth, _ = s.authorize_batch(auths)
    assert batch_auth is not None
    assert s.crypto.counts["T_ZV"] - before == 3 * s.ledger.t  # m requests x t members


def test_shared_evidence_reverifies_shared_nodes_for_every_record(cfg, ds):
    from veredact_bench.evaluation.common import build_history

    s = open_system(cfg, "veredact-shared-evidence", ds)
    build_history(s, ds.trace[:24], 8)
    s.index_records()
    recs = s.p.records[:16]
    accepted, nodes = audit(s, recs)
    assert all(accepted.values())
    assert nodes["auth"] == nodes["trans"] == nodes["cp"] == len(recs)


def test_per_request_and_fixed_batch_take_arrival_order(cfg, ds):
    queue = [(f"v{i}", float(i)) for i in range(100)]  # (validated request, admission time)
    per = open_system(cfg, "veredact-per-request", ds).p
    fixed = open_system(cfg, "veredact-fixed-batch", ds).p
    assert per.select_round(queue, now=200.0, arrival_rate=1000.0) == ["v0"]
    assert fixed.select_round(queue, now=200.0, arrival_rate=1000.0) == [f"v{i}" for i in range(64)]
    assert not fixed.round_ready(63, oldest_wait=10.0, arrival_rate=1.0)  # waits for its static size
    assert fixed.round_ready(64, oldest_wait=0.0, arrival_rate=1.0)


# ---------------------------------------------------------------- rule 6: anchoring is ledger time
def test_anchoring_transaction_is_built_outside_the_phase4_timer(cfg, ds):
    """Phase 4's crypto timer must not contain the anchoring transaction's build and signing: p.authorize
    only records the call, and the scheme submits it after the timer stops (Other/docs/experiments.md rule 6)."""
    s = open_system(cfg, "veredact", ds)
    auths = [validated(s, request_for(ds, s, b)) for b in (0, 1, 2)]
    before = len(s.p.pending_anchor)
    assert s.p.authorize([a.handle for a in auths]) is not None
    assert len(s.p.pending_anchor) == before  # nothing submitted inside the timed call
    s.p.flush_anchors()
    assert len(s.p.pending_anchor) == before + 1  # exactly the abrrr_authorization transaction


def test_execution_defers_its_finalization_transaction(cfg, ds):
    """Phase 5 likewise: execute() records redaction_finalization, redact() submits it after crypto_ms."""
    s = open_system(cfg, "veredact", ds)
    auths = [validated(s, request_for(ds, s, b)) for b in (0, 1)]
    batch_auth, _ = s.authorize_batch(auths)
    before = len(s.p.pending_anchor)
    records = s.p.execute(batch_auth)
    assert records and len(s.p.pending_anchor) == before
    fut = s.p.flush_anchors()
    assert fut is s.p.last_finalization and len(s.p.pending_anchor) == before + 1


def test_phase4_rejects_a_request_whose_attested_commitment_does_not_reconstruct(cfg, ds):
    """C_VR is rebuilt from the request's fields and the attested h_i^PQ, so a tampered h_i^PQ is caught
    even though Phase 4 no longer re-hashes the whole PQZK proof."""
    s = open_system(cfg, "veredact", ds)
    good, bad = (validated(s, request_for(ds, s, b)) for b in (0, 1))
    bad.handle.h_proof = b"\0" * len(bad.handle.h_proof)
    auth = s.p.authorize([good.handle, bad.handle])
    assert [v.RID for v in auth.members] == [good.handle.RID]


# ---------------------------------------------------------------- batched PQCH verification
def test_pqch_is_checked_once_per_distinct_transition(audited):
    """SAVER checks each distinct transition once, and _pqch_batch does all of them in one matrix product:
    the T_CH ops of an audit equal its verified transition nodes."""
    s = audited
    s.p.vcs.clear()
    before = s.crypto.counts["T_CH"]
    accepted, nodes = audit(s, s.p.records[:16])
    assert all(accepted.values())
    assert s.crypto.counts["T_CH"] - before == nodes["trans"]


def test_batched_pqch_rejects_only_the_tampered_transition(audited):
    """Batching must not let one bad column decide for the others: verify_many returns a verdict per column."""
    s = audited
    s.p.vcs.clear()
    recs = [copy.deepcopy(r) for r in s.p.records[:8]]
    bad = recs[3]
    bad.pbrp["r_new"] = bad.pbrp["r_new"] + 1  # a different r_b' no longer satisfies PQCH.Hash(MR_b', r_b') = CH_b
    accepted, _ = audit(s, recs)
    assert accepted[bad.RID] is False
    assert all(ok for rid, ok in accepted.items() if rid != bad.RID)


def test_shared_evidence_still_rechecks_pqch_for_every_record(cfg, ds):
    """The ablation keeps its meaning: Shared-Evidence re-verifies a shared node per dependent record, so it
    pays one T_CH per record where SAVER pays one per distinct transition."""
    from veredact_bench.evaluation.common import build_history

    s = open_system(cfg, "veredact-shared-evidence", ds)
    build_history(s, ds.trace[:24], 8)
    s.index_records()
    recs = s.p.records[:16]
    before = s.crypto.counts["T_CH"]
    accepted, _ = audit(s, recs)
    assert all(accepted.values())
    assert s.crypto.counts["T_CH"] - before == len(recs)


def test_checkpoint_signature_binds_r_through_its_digest(audited):
    """sigma_b signs H(r_b), not r_b itself, so an audit does not re-hash 64 KiB per checkpoint node.
    A checkpoint whose r_b was replaced no longer verifies, because its digest no longer matches."""
    s = audited
    s.p.vcs.clear()
    recs = [copy.deepcopy(r) for r in s.p.records[:6]]
    cp = recs[2].pbrp["cp"]
    assert cp.r_digest == s.crypto.H(cp.r.tobytes())
    recs[2].pbrp = dict(recs[2].pbrp, cp=dataclasses.replace(cp, r_digest=b"\x00" * 32))
    accepted, _ = audit(s, recs)
    assert accepted[recs[2].RID] is False
    assert all(ok for rid, ok in accepted.items() if rid != recs[2].RID)


# ---------------------------------------------------------------- FreshLeaf (#5 step 3)
def prepared(s, req):
    """A request prepared against the state as it is NOW, not submitted yet."""
    return s.p.make_request(req.requester, req.tid, b"new-payload")


def test_freshleaf_accepts_a_request_whose_neighbour_was_redacted(cfg, ds):
    """The point of splitting h_i^st: a redaction of ANOTHER leaf of the same batch no longer invalidates a
    pending request, because h_i^leaf is unchanged and the snapshot it used is still within k."""
    s = open_system(cfg, "veredact", ds)
    mine = request_for(ds, s, 0)
    R = prepared(s, mine)
    redact(s, request_for(ds, s, 0, avoid={mine.tid}))  # neighbour in the SAME batch
    assert s.ledger.batches[0].v > 0
    assert s.p.fresh_leaf(s.ledger.txs[mine.tid], R.h_st) == 0  # validated against snapshot v_b = 0


def test_freshleaf_rejects_a_request_whose_own_leaf_was_redacted(cfg, ds):
    """Condition (2): the target's own leaf must be unchanged. This is the conflict FreshLeaf must still catch."""
    s = open_system(cfg, "veredact", ds)
    mine = request_for(ds, s, 0)
    R = prepared(s, mine)
    redact(s, mine)
    assert s.p.fresh_leaf(s.ledger.txs[mine.tid], R.h_st) is None


def test_freshleaf_rejects_a_snapshot_older_than_k(cfg, ds):
    """Condition (3): the snapshot must be anchored AND within k versions of the current one."""
    s = open_system(cfg, "veredact", ds)
    s.p.k = 1
    mine = request_for(ds, s, 0)
    R = prepared(s, mine)
    others = [r for r in ds.trace if not r.fault and r.tid != mine.tid and s.ledger.txs[r.tid].b == 0][:2]
    redact(s, others[0])
    assert s.p.fresh_leaf(s.ledger.txs[mine.tid], R.h_st) == 0  # one version old: inside the window
    redact(s, others[1])
    assert s.p.fresh_leaf(s.ledger.txs[mine.tid], R.h_st) is None  # two versions old: outside it


def test_freshleaf_rejects_a_snapshot_that_was_never_anchored(cfg, ds):
    """Condition (3): a snapshot the requester invented, of the right shape, is not an anchored checkpoint."""
    s = open_system(cfg, "veredact", ds)
    mine = request_for(ds, s, 0)
    tx = s.ledger.txs[mine.tid]
    forged = s.crypto.H(s.p.leaf_digest(tx), s.crypto.H(b"not-an-anchored-snapshot"))
    assert s.p.fresh_leaf(tx, forged) is None


def test_pbrp_records_the_snapshot_the_request_was_validated_against(cfg, ds):
    """v_snap goes into PBRP_i and into h_i^PBRP, so an audit can check validation used a recent snapshot."""
    s = open_system(cfg, "veredact", ds)
    mine = request_for(ds, s, 0)
    res = redact(s, mine)
    assert res.outcomes[0].ok
    rr = s.p.records[-1]
    assert rr.pbrp["v_snap"] == 0 and rr.v_b - s.p.k <= rr.pbrp["v_snap"] <= rr.v_b


# ---------------------------------------------------------------- BatchAttest (P2: #6 step 3 O3 = #7 step 3 O4)
def _windowed(cfg, W, ms=60_000):
    c = copy.deepcopy(cfg)
    c["veredact"]["vps_window"], c["veredact"]["vps_window_ms"] = W, ms
    return c


def _distinct_targets(s, ds, n):
    out, seen = [], set()
    for r in ds.trace:
        if not r.fault and r.tid not in seen:
            out.append(r)
            seen.add(r.tid)
        if len(out) == n:
            return out
    raise LookupError("not enough distinct targets")


def test_batchattest_signs_once_per_admission_window(cfg, ds):
    """The VPS signs one Merkle root per window of W admissions (alpha_i = window root + membership path),
    instead of one ML-DSA attestation and one receipt per request. Every member verifies against it, and the
    receipt rc_i is the same attestation."""
    s = open_system(_windowed(cfg, 4), "veredact", ds)
    vrs = [validated(s, r).handle for r in _distinct_targets(s, ds, 8)]
    assert len(s.p.windows) == 2 and len({(v.att.w, v.att.sigma) for v in vrs}) == 2
    assert all(s.p.att_verify(v) for v in vrs)
    assert all(v.receipt[1] is v.att for v in vrs)
    s.teardown()


def test_batchattest_rejects_a_path_from_another_member(cfg, ds):
    """A membership path that does not lead from this request's own leaf to the signed root is rejected, in
    att_verify and therefore in Phase 4 (the request leaves the round)."""
    s = open_system(_windowed(cfg, 4), "veredact", ds)
    a, b, c_, d = (validated(s, r).handle for r in _distinct_targets(s, ds, 4))
    a.att = dataclasses.replace(a.att, path=b.att.path, index=b.att.index)
    assert not s.p.att_verify(a) and s.p.att_verify(b)
    auth = s.p.authorize([a, b, c_, d])
    assert a.RID not in {v.RID for v in auth.members} and len(auth.members) == 3
    s.teardown()


def test_phase4_closes_an_open_window_instead_of_waiting(cfg, ds):
    """A round may select requests whose window has not filled yet: Phase 4 closes that window (one more
    signature, never fewer than the protocol needs) rather than waiting for W admissions or T_vps."""
    s = open_system(_windowed(cfg, 256), "veredact", ds)
    vrs = [validated(s, r).handle for r in _distinct_targets(s, ds, 3)]
    assert not s.p.windows and not any(v.att.sigma for v in vrs)
    auth = s.p.authorize(vrs)
    assert len(auth.members) == 3 and len(s.p.windows) == 1
    s.teardown()


def test_window_closes_after_its_time_bound(cfg, ds):
    """T_vps bounds the wait: with T_vps = 0 every new admission closes the window before it."""
    s = open_system(_windowed(cfg, 256, ms=0), "veredact", ds)
    for r in _distinct_targets(s, ds, 3):
        validated(s, r)
    assert len(s.p.windows) == 2  # the third admission is still in the open window
    s.teardown()


def test_saver_verifies_each_window_signature_once_per_query(audited):
    """The window signature is shared evidence: SAVER verifies it once per distinct window in the query;
    Shared-Evidence re-verifies it for every record."""
    s = audited
    recs = s.p.records[:24]
    windows = len({r.pbrp["vr"].att.w for r in recs})
    s.p.vcs.clear()
    accepted, nodes = audit(s, recs)
    assert all(accepted.values()) and nodes["win"] == windows < len(recs)
    s.p.audit_mode = "shared"
    try:
        s.p.vcs.clear()
        accepted, nodes = audit(s, recs)
        assert all(accepted.values()) and nodes["win"] == len(recs)
    finally:
        s.p.audit_mode = "saver"
