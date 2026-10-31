# HSM API Security Lab

[![Tests and dashboard](https://github.com/artysficial/hsm-api-security-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/artysficial/hsm-api-security-lab/actions/workflows/tests.yml)
[![Dashboard](https://img.shields.io/badge/dashboard-live-0071e3)](https://artysficial.github.io/hsm-api-security-lab/)

Automated security testing of a **payment HSM REST API**, the kind of interface banks put in front of their Hardware
Security Modules for key management, PIN translation and MAC. Every run publishes a security dashboard with a
release verdict, OWASP coverage, findings and requirement traceability.

**[View the live dashboard →](https://artysficial.github.io/hsm-api-security-lab/)**

> The system under test is a **simulated** HSM (`hsm_api/`), modelled on the command families of real payment
> HSMs such as Thales payShield, so the suite runs anywhere without hardware or vendor credentials. The
> cryptography is simulated; the security behaviour under test is real. Not affiliated with any vendor.

## What is tested

| Area | Examples | Requirement |
| --- | --- | --- |
| API1 Broken object level authorization | another client's key is invisible (404, not 403); no use of foreign keys | REQ-HSM-04 |
| API2 Broken authentication | no token, expired, tampered, `alg: none`, wrong signing key; uniform errors; lockout | REQ-HSM-01, 02, 12 |
| API3 Property level authorization | clear key material never returned; `owner`/`usage`/`exportable` cannot be mass-assigned | REQ-HSM-05 |
| API4 Resource consumption | per-client rate limit on crypto calls; 16 KB body limit | REQ-HSM-11, 14 |
| API5 Function level authorization | scope matrix per client role (least privilege) | REQ-HSM-03 |
| API8 Misconfiguration | HSTS, nosniff, no-store, CSP, no server banner, no wildcard CORS | REQ-HSM-13 |
| Injection & errors | SQLi / traversal / XSS / JNDI payloads rejected without reflection or stack traces | REQ-HSM-09 |
| Cryptographic controls | key usage enforcement, ISO-0/ISO-4 PIN block validation, MAC tamper detection | REQ-HSM-06, 07, 08 |
| Audit logging | every sensitive and refused operation logged, never PINs or message data | REQ-HSM-10 |

59 tests; the suite runs over real HTTP against the API (start-up handled in `tests/conftest.py`). Point it at
another deployment with `HSM_BASE_URL`.

## Findings

Two weaknesses are seeded in the simulator so the suite proves it catches real issues. Each has an automated
reproduction marked as a strict expected failure: when the fix lands, the build turns red until the finding is
re-verified and closed.

| ID | Severity | Finding |
| --- | --- | --- |
| HSM-SEC-001 | Medium | No lockout after repeated failed client authentication (REQ-HSM-12) |
| HSM-SEC-002 | Low | `Strict-Transport-Security` header missing (REQ-HSM-13) |

## Run it

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest                                   # writes reports/results.json and reports/junit.xml
python tools/build_dashboard.py                    # writes site/index.html
python -m hsm_api                                  # run the API on :8443 (docs at /docs)
```

## Part of a case study

This project is the SDET lens on the fictional **Arunika Bank payment-security programme**. The requirement IDs
come from the programme's BRD in [requirements-traceability](https://github.com/artysficial/requirements-traceability),
which pulls this dashboard's `results.json` to build its traceability matrix.

Built by [Rahmadani Tyas Ningrum](https://artysficial.github.io/) · MIT licence
