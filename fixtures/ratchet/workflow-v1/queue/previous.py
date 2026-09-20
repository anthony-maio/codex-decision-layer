def ready_jobs(jobs, now, limit=None):
    ready = [job for job in jobs if job["state"] == "queued" and job["ready_at"] < now]
    ready.sort(key=lambda job: job["priority"])
    return [job["id"] for job in ready][:limit]
