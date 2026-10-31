"""pytest plugin: writes reports/results.json for the dashboard.

Tests describe themselves with markers:
    @pytest.mark.req("REQ-HSM-04")          requirement(s) the test verifies
    @pytest.mark.category("API1 BOLA")      grouping on the dashboard
    @pytest.mark.severity("high")           impact if the test fails
    @pytest.mark.defect("HSM-SEC-001")      known, logged defect (use with xfail(strict=True))
The first line of the docstring becomes the test's title.
"""

from __future__ import annotations

import json
import os
import time

import pytest

_results: list[dict] = []
_started = time.time()


def pytest_configure(config):
    for name in ("req", "category", "severity", "defect"):
        config.addinivalue_line("markers", f"{name}(value): dashboard metadata")


def _marker_values(item, name):
    return [str(arg) for mark in item.iter_markers(name) for arg in mark.args]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # record the call phase, or setup when it did not pass (skips and errors happen there);
    # attempts that pytest-rerunfailures retries are not results
    if report.outcome == "rerun":
        return
    if report.when != "call" and not (report.when == "setup" and report.outcome != "passed"):
        return

    status = report.outcome
    if hasattr(report, "wasxfail"):
        status = "known defect" if report.skipped else "fixed defect"
    elif report.when == "setup" and report.failed:
        status = "error"

    doc = (item.function.__doc__ or "").strip().splitlines()
    reason = ""
    if report.skipped and isinstance(report.longrepr, tuple):
        reason = str(report.longrepr[2]).replace("Skipped: ", "")
    elif report.failed:
        reason = str(report.longrepr).strip().splitlines()[-1][:300] if report.longrepr else ""

    _results.append({
        "id": item.nodeid,
        "title": doc[0] if doc else item.name.replace("_", " "),
        "module": item.module.__name__.split(".")[-1],
        "status": status,
        "duration": round(report.duration, 3),
        "requirements": _marker_values(item, "req"),
        "category": (_marker_values(item, "category") or ["General"])[0],
        "severity": (_marker_values(item, "severity") or ["medium"])[0],
        "defect": (_marker_values(item, "defect") or [None])[0],
        "reason": reason,
    })


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("RESULTS_JSON", "reports/results.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    counts: dict[str, int] = {}
    for result in _results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({
            "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration": round(time.time() - _started, 2),
            "counts": counts,
            "tests": _results,
        }, handle, indent=2)
