VALID_STATES = {"queued", "running", "done"}


def ready_jobs(jobs, now, limit=None):
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("invalid limit")
    seen = set()
    for job in jobs:
        if job["state"] not in VALID_STATES or job["id"] in seen:
            raise ValueError("invalid job")
        seen.add(job["id"])
    ready = [job for job in jobs if job["state"] == "queued" and job["ready_at"] <= now]
    ready.sort(key=lambda job: (-job["priority"], job["ready_at"]))
    return [job["id"] for job in ready][:limit]
