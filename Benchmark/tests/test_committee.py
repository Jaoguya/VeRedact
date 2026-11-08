"""Committee fairness fix (#5 step 2, #13): t committee members are separate machines and talk over the network.
Every threshold scheme (VeRedact-PQ, Schemes [1] and [27]) runs its members through one CommitteeClock: each
member's work is timed on its own, a step's crypto time counts the SLOWEST member, and each message round waits
for real until (slowest member + message delay) of wall time has passed; that wait is network time, not crypto."""

import copy

import pytest

from veredact_bench.methods.committee import CommitteeClock
from veredact_bench.utils.config import load


@pytest.fixture(scope="module")
def cfg_small():
    c = copy.deepcopy(load("smoke"))
    c["dataset"]["base_transactions"] = 1024  # test fixture size, not an experiment parameter
    return c


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s


def member(ft, seconds, value):
    def work():
        ft.t += seconds
        return value

    return work


def test_slowest_member_counts_and_the_round_waits_for_the_delay():
    ft = FakeTime()
    cc = CommitteeClock(delay_ms=10, clock=ft.clock, sleep=ft.sleep)
    out = cc.round([member(ft, 0.001, "a"), member(ft, 0.003, "b"), member(ft, 0.002, "c")])
    assert out == ["a", "b", "c"]
    assert abs(ft.t - 0.013) < 1e-12  # wall: slowest member (3 ms) + 10 ms delay, as on separate machines
    credit_s, net_ms = cc.take()
    assert abs(credit_s - (0.013 - 0.003)) < 1e-12  # elapsed - credit = the slowest member only
    assert net_ms == 10.0 and cc.rounds == 1
    assert cc.take() == (0.0, 0.0)  # taken once


def test_serial_work_longer_than_the_delay_is_not_waited_twice():
    """Members run in turn here; when their sum already exceeds slowest + delay, no extra wait is added (the
    wall time stays conservative for heavy members), and crypto time still counts only the slowest member."""
    ft = FakeTime()
    cc = CommitteeClock(delay_ms=10, clock=ft.clock, sleep=ft.sleep)
    cc.round([member(ft, 0.020, 1), member(ft, 0.020, 2)])
    assert abs(ft.t - 0.040) < 1e-12
    credit_s, net_ms = cc.take()
    assert abs((0.040 - credit_s) - 0.020) < 1e-12 and net_ms == 10.0


def test_off_switch_is_the_serial_sum():
    """parallel_members: false is the old harness: members summed and no message delay (with a delay set, the
    round must not sleep, or the sleep would be counted as crypto time)."""
    ft = FakeTime()
    cc = CommitteeClock(delay_ms=10, parallel=False, clock=ft.clock, sleep=ft.sleep)
    cc.round([member(ft, 0.001, 1), member(ft, 0.002, 2)])
    assert cc.take() == (0.0, 0.0) and abs(ft.t - 0.003) < 1e-12
    assert abs(cc.last_slowest_ms() - 3.0) < 1e-9  # the step's crypto time is the serial sum


def test_an_oversleep_is_not_counted_as_crypto_time():
    """The OS may sleep longer than asked; the credit is the wait that really passed, so the extra time is
    network time, not crypto time charged once per round (that would hurt schemes with more rounds)."""
    ft = FakeTime()

    def oversleep(s):
        ft.t += s + 0.004  # 4 ms late

    cc = CommitteeClock(delay_ms=10, clock=ft.clock, sleep=oversleep)
    cc.round([member(ft, 0.001, 1), member(ft, 0.002, 2)])
    credit_s, _ = cc.take()
    assert abs((ft.t - credit_s) - 0.002) < 1e-12  # crypto = the slowest member, exactly


def test_every_threshold_scheme_uses_two_message_rounds_where_its_paper_has_them(cfg_small):
    """VeRedact-PQ: approvals + PQCH shares, two rounds per authorization round of m requests. Scheme [1]: the
    approving full nodes' checks + the collision shares, two per redaction. Scheme [27]: Adapt's two rounds via
    the Commitment Aggregator, per redaction."""
    from veredact_bench.data.dataset import build_dataset
    from veredact_bench.evaluation.common import authorize, open_system, prepare

    ds = build_dataset(cfg_small, n_requests=12)
    for key, reqs, rounds in (("veredact", 4, 2), ("S1", 2, 4), ("S27", 2, 4)):
        s = open_system(cfg_small, key, ds)
        before = s.committee.rounds
        targets, seen = [], set()
        for r in ds.trace:  # distinct targets (Scheme [1]: distinct blocks, one redaction per block)
            unit = s.block_of[r.tid][0] if hasattr(s, "block_of") else r.tid
            if not r.fault and unit not in seen:
                targets.append(r)
                seen.add(unit)
            if len(targets) == reqs:
                break
        auths = [authorize(s, r, prepare(s, r)) for r in targets]
        res = s.redact(auths)
        assert all(o.ok for o in res.outcomes), key
        assert s.committee.rounds - before == rounds, key
        # every round's delay reaches the results as network time (Scheme [1]: half of it in its authorizations)
        net = res.net_ms + sum(a.net_ms for a in auths)
        assert net == rounds * s.committee.delay_ms, key
        assert s.committee.take() == (0.0, 0.0), key  # no credit left to leak into a later timed section
        s.teardown()
