# Repair ready-job selection

Two failed attempts are recorded in the supplied history. Repair product.py;
keep the existing tests unchanged and run them.

VALID_STATES must contain queued, running, and done. ready_jobs(jobs, now, limit=None)
returns the IDs of queued jobs whose ready_at is at most now. Order by higher
priority first, then earlier ready_at, then original input order for exact ties.
Apply limit after sorting; None means unlimited, zero means no jobs. A supplied
limit must be a nonnegative integer, excluding bool, or raise ValueError.

Job IDs must be unique across the whole input, including jobs not yet ready or
not queued. Duplicate IDs and unknown states raise ValueError, even when limit
is zero. The inputs are otherwise well-formed dictionaries with string id/state,
integer priority, and numeric ready_at/now. Do not modify the input list or its
dictionaries. Do not restart running or completed jobs.
