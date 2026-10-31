"""Turns reports/results.json into the published security dashboard (site/index.html)."""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_kit as rk  # noqa: E402

REQUIREMENTS = json.loads((ROOT / "docs" / "requirements.json").read_text(encoding="utf-8"))
FINDINGS = json.loads((ROOT / "docs" / "findings.json").read_text(encoding="utf-8"))
OWASP = [
    ("API1 BOLA", "Broken object level authorization"),
    ("API2 Broken authentication", "Broken authentication"),
    ("API3 Property level authorization", "Broken object property level authorization"),
    ("API4 Resource consumption", "Unrestricted resource consumption"),
    ("API5 Function level authorization", "Broken function level authorization"),
    ("API8 Security misconfiguration", "Security misconfiguration"),
    ("Injection & error handling", "Injection, error handling (API8/API10)"),
    ("Cryptographic controls", "Key usage, PIN and MAC controls"),
    ("Audit logging", "Audit trail (supports API9 inventory/logging)"),
]


def requirement_status(tests: list[dict]) -> str:
    statuses = {t["status"] for t in tests}
    if not tests:
        return "Not covered"
    if statuses & {"failed", "error", "known defect"}:
        return "Not met"
    if statuses <= {"passed"}:
        return "Met"
    return "Partial"


def main() -> None:
    results = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
    tests = results["tests"]
    counts = Counter(t["status"] for t in tests)
    executed = [t for t in tests if t["status"] != "skipped"]
    passed = counts["passed"]
    unexpected = counts["failed"] + counts["error"] + counts["fixed defect"]

    open_findings = [f for f in FINDINGS if f["status"] == "Open"]
    severe_open = [f for f in open_findings if f["severity"] in ("Critical", "High")]
    if unexpected or severe_open:
        verdict = ("No-go: unexpected failures or high-severity findings", "bad")
    elif open_findings:
        verdict = (f"Conditional go: {len(open_findings)} medium/low findings with remediation plans", "warn")
    else:
        verdict = ("Go: all security requirements met", "ok")

    by_req = defaultdict(list)
    for t in tests:
        for req in t["requirements"]:
            by_req[req].append(t)
    req_rows = []
    met = 0
    for req in REQUIREMENTS:
        status = requirement_status(by_req[req["id"]])
        met += status == "Met"
        req_rows.append([req["id"], req["title"], len(by_req[req["id"]]), rk.pill(status)])

    by_category = defaultdict(Counter)
    for t in tests:
        by_category[t["category"]][t["status"]] += 1

    severity_tone = {"Critical": "bad", "High": "bad", "Medium": "warn", "Low": "neutral"}
    findings_rows = [
        [f["id"], rk.pill(f["severity"]) if f["severity"] != "Low" else '<span class="pill neutral">Low</span>', f["title"], f["requirement"], f["owasp"], f["remediation"], rk.pill(f["status"])]
        for f in FINDINGS
    ]

    body = rk.kpis([
        ("Security tests", len(tests), f"{len(executed)} executed in {results['duration']:.0f}s"),
        ("Passed", passed, f"{100 * passed / max(1, len(executed)):.0f}% of executed", "ok"),
        ("Open findings", len(open_findings), ", ".join(f"{n} {s.lower()}" for s, n in Counter(f["severity"] for f in open_findings).items()) or "none", "warn" if open_findings else "ok"),
        ("Requirements met", f"{met}/{len(REQUIREMENTS)}", "from the HSM API BRD", "ok" if met == len(REQUIREMENTS) else "warn"),
        ("Unexpected failures", unexpected, "regressions since last run", "bad" if unexpected else "ok"),
    ])
    body += rk.grid(
        rk.section("Results", rk.donut([
            ("Passed", passed, "var(--green)"),
            ("Known defects", counts["known defect"], "var(--orange)"),
            ("Failed", counts["failed"] + counts["error"], "var(--red)"),
            ("Skipped", counts["skipped"], "var(--line)"),
        ], center=f"{100 * passed / max(1, len(executed)):.0f}%", caption="pass rate")),
        rk.section("Coverage by OWASP API Security Top 10", rk.bars(
            [(name, sum(by_category[name].values())) for name, _ in OWASP], unit=" tests"),
            "Each category maps to OWASP API Security Top 10 (2023) or a payment-HSM control."),
    )
    body += rk.section("Findings", rk.table(["ID", "Severity", "Finding", "Requirement", "OWASP", "Remediation", "Status"], findings_rows, {1, 6}),
                       "Each finding has an automated reproduction that runs as a strict expected failure: when the fix lands, the build turns red until the finding is re-verified and closed.")
    body += rk.section("Requirements traceability", rk.table(["Requirement", "Description", "Tests", "Status"], req_rows, {3}),
                       "Requirement IDs come from the programme's Business Requirement Document (see the Business Analyst dashboard).")
    category_rows = [
        [name, desc, c["passed"], c["known defect"], c["failed"] + c["error"], c["skipped"]]
        for name, desc in OWASP if (c := by_category[name])
    ]
    body += rk.section("Results by category", rk.table(["Category", "Scope", "Passed", "Known defects", "Failed", "Skipped"], category_rows))
    test_rows = [[t["title"], t["category"], t["severity"].title(), ", ".join(t["requirements"]), rk.pill(t["status"])] for t in tests]
    body += rk.section("All tests", rk.table(["Test", "Category", "Severity", "Requirements", "Result"], test_rows, {4}))

    html = rk.page(
        title="HSM API Security Testing",
        eyebrow="SDET · Security testing",
        summary="Automated security tests against a simulated payment HSM REST API: OWASP API Top 10, key usage, PIN and MAC controls, audit logging and transport hardening.",
        body=body,
        repo="hsm-api-security-lab",
        verdict=verdict,
    )
    out = ROOT / "site"
    rk.write(str(out / "index.html"), html)
    shutil.copy(ROOT / "reports" / "results.json", out / "results.json")
    print(f"dashboard: {out / 'index.html'} ({passed} passed, {len(open_findings)} open findings)")


if __name__ == "__main__":
    main()
