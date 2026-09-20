def replay(events, start_seq=0, initial=0):
    if type(start_seq) is not int or start_seq < 0 or type(initial) is not int:
        raise ValueError("invalid starting state")
    expected = start_seq + 1
    total = initial
    seen = {}
    for event in events:
        if not isinstance(event, dict) or not {"seq", "delta"} <= event.keys():
            raise ValueError("invalid event")
        seq, delta = event["seq"], event["delta"]
        if type(seq) is not int or type(delta) is not int:
            raise ValueError("invalid event values")
        if seq in seen:
            if seen[seq] != delta:
                raise ValueError("conflicting retry")
            continue
        if seq != expected:
            raise ValueError("event sequence invalid")
        seen[seq] = delta
        total += delta
        expected += 1
    return total
