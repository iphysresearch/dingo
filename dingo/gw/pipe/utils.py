def _strip_unwanted_submission_keys(job):
    job.getenv = None
    job.universe = None
    extra_lines = [
        line
        for line in job.extra_lines
        if not line.startswith("priority")
        and not line.startswith("accounting_group")
    ]
    job.extra_lines = extra_lines
