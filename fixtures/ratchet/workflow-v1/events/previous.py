def invalid_event():
    raise ValueError("event sequence invalid")


def replay(events, start_seq=0, initial=0):
    expected = start_seq + 1
    total = initial
    seen = set()
    for event in events:
        seq = event["seq"]
        if seq in seen:
            invalid_event()
        if seq != expected + 1:
            invalid_event()
        seen.add(seq)
        total += event["delta"]
        expected += 1
    return total
