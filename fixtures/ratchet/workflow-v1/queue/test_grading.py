from copy import deepcopy
import pytest
from product import ready_jobs, VALID_STATES


def job(identity, priority=1, ready_at=0, state="queued"):
    return dict(id=identity, priority=priority, ready_at=ready_at, state=state)


@pytest.mark.parametrize("jobs,now,limit,expected", [
    ([], 1, None, []),
    ([job("boundary", ready_at=5)], 5, None, ["boundary"]),
    ([job("future", priority=100, ready_at=6), job("ready")], 5, None, ["ready"]),
    ([job("low"), job("high", 9)], 5, None, ["high", "low"]),
    ([job("later", 2, 4), job("earlier", 2, 1)], 5, None, ["earlier", "later"]),
    ([job("z"), job("a"), job("m")], 5, None, ["z", "a", "m"]),
    ([job("low"), job("high", 9)], 5, 1, ["high"]),
    ([job("ready")], 5, 0, []),
    ([job("active", state="running"), job("old", state="done"), job("ready")], 5, None, ["ready"]),
    ([job("negative", -3), job("zero", 0)], 5, 99, ["zero", "negative"]),
])
def test_order(jobs, now, limit, expected):
    before = deepcopy(jobs)
    assert ready_jobs(jobs, now, limit) == expected
    assert jobs == before


@pytest.mark.parametrize("limit", [-1, True, False, 1.5, "2"])
def test_limit(limit):
    with pytest.raises(ValueError):
        ready_jobs([], 0, limit)


@pytest.mark.parametrize("jobs", [
    [job("same"), job("same")],
    [job("same"), job("same", state="done")],
    [job("same", ready_at=100), job("same", ready_at=200)],
    [job("unknown", state="waiting")],
])
@pytest.mark.parametrize("limit", [None, 0])
def test_invalid_jobs(jobs, limit):
    with pytest.raises(ValueError):
        ready_jobs(jobs, 0, limit)


def test_states():
    assert VALID_STATES == {"queued", "running", "done"}
