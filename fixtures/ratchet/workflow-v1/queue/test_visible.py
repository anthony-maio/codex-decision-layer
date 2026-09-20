import pytest
import product


@pytest.fixture
def queue():
    assert product.VALID_STATES == {"queued", "running", "done"}
    return [{"id": "low", "state": "queued", "ready_at": 2, "priority": 1},
            {"id": "high", "state": "queued", "ready_at": 3, "priority": 9}]


def test_ready(queue):
    assert product.ready_jobs(queue, now=3) == ["high", "low"]
