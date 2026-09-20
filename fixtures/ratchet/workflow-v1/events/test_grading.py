from copy import deepcopy
import pytest
from product import replay


def event(seq, delta):
    return dict(seq=seq, delta=delta)


@pytest.mark.parametrize("events,start,initial,expected", [
    ([], 0, 7, 7),
    ([event(1, 3)], 0, 0, 3),
    ([event(1, 3), event(2, -5)], 0, 1, -1),
    ([event(1, 3), event(1, 3), event(2, -1)], 0, 0, 2),
    ([event(1, 3), event(2, -1), event(1, 3), event(3, 7)], 0, 0, 9),
    ([event(11, 2), event(11, 2), event(12, 4)], 10, 100, 106),
    ([event(1, 0), event(1, 0)], 0, -5, -5),
])
def test_replay(events, start, initial, expected):
    before = deepcopy(events)
    result = replay(events, start, initial)
    assert type(result) is int and result == expected
    assert events == before


@pytest.mark.parametrize("events,start", [
    ([event(1, 3), event(1, 4)], 0),
    ([event(1, 3), event(2, 4), event(1, 5)], 0),
    ([event(2, 1)], 0),
    ([event(1, 1), event(3, 1)], 0),
    ([event(10, 1)], 10),
    ([event(0, 1)], 0),
    ([event(-1, 1)], 0),
    ([event(True, 1)], 0),
    ([event(1, True)], 0),
    ([event(1, 1), event(1, True)], 0),
    ([event(1.0, 1)], 0),
    ([event(1, "2")], 0),
    ([{}], 0),
    ([{"seq": 1}], 0),
    ([None], 0),
])
def test_invalid_event(events, start):
    with pytest.raises(ValueError):
        replay(events, start)


@pytest.mark.parametrize("start,initial", [(-1, 0), (True, 0), (1.5, 0), (0, True), (0, "1"), (0, 1.5)])
def test_invalid_initial(start, initial):
    with pytest.raises(ValueError):
        replay([], start, initial)
