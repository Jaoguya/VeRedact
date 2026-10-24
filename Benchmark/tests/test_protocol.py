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
    queue = [cand(b"B", 1, 0), cand(b"A0", 0, 0), cand(b"C", 2, 0), cand(b"A1", 0, 1), cand(b"D", 3, 0), cand(b"A2", 0, 2)]
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
