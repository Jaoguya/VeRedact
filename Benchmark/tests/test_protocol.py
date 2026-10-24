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
