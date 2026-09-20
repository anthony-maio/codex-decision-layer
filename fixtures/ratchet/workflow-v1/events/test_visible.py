from product import replay


def test_replay():
    assert replay([{"seq": 1, "delta": 3}, {"seq": 1, "delta": 3},
                   {"seq": 2, "delta": -1}]) == 2
