"""OWASP API8:2023 Security Misconfiguration."""

import pytest

pytestmark = pytest.mark.category("API8 Security misconfiguration")


@pytest.mark.req("REQ-HSM-13")
@pytest.mark.severity("medium")
@pytest.mark.parametrize("header, expected", [("x-content-type-options", "nosniff"), ("cache-control", "no-store")])
def test_security_headers_are_set(api, header, expected):
    """Responses carry nosniff and no-store headers"""
    assert api.get("/health").headers.get(header) == expected


@pytest.mark.req("REQ-HSM-13")
@pytest.mark.severity("low")
def test_content_security_policy_is_locked_down(api):
    """A restrictive Content-Security-Policy is sent"""
    assert "default-src 'none'" in api.get("/health").headers.get("content-security-policy", "")


@pytest.mark.req("REQ-HSM-13")
@pytest.mark.severity("low")
def test_server_software_is_not_advertised(api):
    """The server does not advertise its software or version"""
    headers = api.get("/health").headers
    assert "server" not in headers and "x-powered-by" not in headers


@pytest.mark.req("REQ-HSM-13")
@pytest.mark.severity("high")
def test_cors_does_not_allow_any_origin(api):
    """Cross-origin requests from arbitrary sites are not allowed"""
    response = api.options("/v1/keys", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert response.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")


@pytest.mark.req("REQ-HSM-13")
@pytest.mark.severity("low")
@pytest.mark.defect("HSM-SEC-002")
@pytest.mark.xfail(strict=True, reason="HSM-SEC-002: Strict-Transport-Security header missing")
def test_hsts_is_enforced(api):
    """Strict-Transport-Security is sent so clients never fall back to HTTP"""
    assert "max-age=" in api.get("/health").headers.get("strict-transport-security", "")
