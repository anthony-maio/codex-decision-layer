# Repair event replay

Two failed attempts are recorded in the supplied history. Repair product.py;
keep the existing tests unchanged and run them.

replay(events, start_seq=0, initial=0) applies integer deltas to an integer initial
value. The first new event must have seq start_seq + 1, followed by contiguous
sequence numbers. Input events are dictionaries with integer seq and delta;
bool is invalid for all integer arguments. start_seq must be nonnegative.

An event whose seq has already appeared in this input is an allowed retry only
when its delta is identical; ignore it without advancing the sequence or changing
the total. Identical retries may appear after later events. Reject a conflicting
retry, a sequence gap, or a seq at or below start_seq that has not appeared in
this input. Raise ValueError for invalid data, missing fields, non-dictionary
events, invalid start_seq, or invalid initial. Validate duplicates as carefully
as new events. Empty input returns initial. Do not modify the input data.
