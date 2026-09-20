"""Opt-in pytest reporter preserving exact reports in a new local JSONL file.

Example: pytest -p evidence_selector.ratchet.pytest_reporter
                --ratchet-output .ratchet/attempt-1.jsonl --ratchet-task example
"""
from __future__ import annotations

import json
from pathlib import Path
import time
import uuid


def pytest_addoption(parser):
    parser.addoption("--ratchet-output", default=None, help="New private Ratchet JSONL evidence path")
    parser.addoption("--ratchet-task", default=None, help="Explicit task identity shared by related attempts")


def pytest_configure(config):
    output = config.getoption("--ratchet-output")
    if output:
        if not config.getoption("--ratchet-task"):
            import pytest
            raise pytest.UsageError("--ratchet-output requires --ratchet-task")
        # xdist workers cannot safely share a run file in this first version.
        if hasattr(config, "workerinput") or getattr(config.option, "numprocesses", 0):
            raise ValueError("Ratchet reporter does not yet support pytest-xdist")
        config.pluginmanager.register(Recorder(Path(output), config), "ratchet-recorder")


class Recorder:
    def __init__(self, output, config):
        output.parent.mkdir(parents=True, exist_ok=True)
        self.stream = output.open("x", encoding="utf-8", newline="\n")
        self.run_id = uuid.uuid4().hex
        self.started = time.monotonic()
        options = []
        skip = False
        for arg in config.invocation_params.args:
            if skip:
                skip = False
            elif arg in ("--ratchet-output", "--ratchet-task"):
                skip = True
            elif not arg.startswith(("--ratchet-output=", "--ratchet-task=")):
                options.append(arg)
        self.write("start", schema=1, root=str(config.rootpath.resolve()), runner="pytest",
                   task=config.getoption("--ratchet-task"), options=options)

    def pytest_collection_finish(self, session):
        self.write("selection", nodeids=[item.nodeid for item in session.items])

    def write(self, kind, **fields):
        self.stream.write(json.dumps({"kind": kind, "run_id": self.run_id, **fields}) + "\n")
        self.stream.flush()

    def pytest_collectreport(self, report):
        if report.failed:
            self.write("report", nodeid=report.nodeid, stage="collection", outcome="failed",
                       longrepr=report.longreprtext, sections=list(report.sections), duration=0)

    def pytest_runtest_logreport(self, report):
        self.write("report", nodeid=report.nodeid, stage=report.when, outcome=report.outcome,
                   longrepr=report.longreprtext, sections=list(report.sections), duration=report.duration)

    def pytest_sessionfinish(self, session, exitstatus):
        self.write("finish", exit_code=int(exitstatus), collected=session.testscollected,
                   duration_seconds=time.monotonic() - self.started)

    def pytest_unconfigure(self, config):
        self.stream.close()
