"""OWASP API2:2023 Broken Authentication."""

import base64
import json
import time

import jwt
import pytest

from hsm_api import config

pytestmark = pytest.mark.category("API2 Broken authentication")


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


@pytest.mark.req("REQ-HSM-02")
@pytest.mark.severity("critical")
def test_endpoints_require_a_token(api):
    """Protected endpoints refuse requests without a bearer token"""
    for method, path in [("GET", "/v1/keys/key_0000000000000000"), ("POST", "/v1/keys"), ("POST", "/v1/mac/generate"), ("GET", "/v1/audit")]:
        response = api.request(method, path, json={} if method == "POST" else None)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
        assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.req("REQ-HSM-01")
@pytest.mark.severity("high")
def test_wrong_secret_and_unknown_client_get_the_same_answer(api):
    """Wrong secret and unknown client are indistinguishable (no client enumeration)"""
    wrong = api.post("/v1/auth/token", json={"client_id": "payments-switch", "client_secret": "guess"})
    unknown = api.post("/v1/auth/token", json={"client_id": "nobody", "client_secret": "guess"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.req("REQ-HSM-01")
@pytest.mark.severity("medium")
def test_tokens_expire_after_fifteen_minutes(api):
    """Issued tokens are short-lived (15 minutes)"""
    response = api.post("/v1/auth/token", json={"client_id": "card-issuing", "client_secret": "issuing-demo-secret"})
    claims = jwt.decode(response.json()["access_token"], options={"verify_signature": False})
    assert response.json()["expires_in"] == 900
    assert claims["exp"] - claims["iat"] == 900


@pytest.mark.req("REQ-HSM-01")
@pytest.mark.severity("high")
def test_expired_token_is_rejected(api):
    """An expired token is refused"""
    past = int(time.time()) - 3600
    expired = jwt.encode({"sub": "payments-switch", "scope": "keys:read", "iat": past - 900, "exp": past}, config.SIGNING_KEY, algorithm="HS256")
    assert api.get("/v1/audit", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


@pytest.mark.req("REQ-HSM-02", "REQ-HSM-03")
@pytest.mark.severity("critical")
def test_tampered_token_cannot_escalate_scope(api, token):
    """Editing the token payload to add scopes breaks the signature"""
    header, payload, signature = token("payments-switch").split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["scope"] += " audit:read"
    forged = f"{header}.{b64(claims)}.{signature}"
    assert api.get("/v1/audit", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


@pytest.mark.req("REQ-HSM-02")
@pytest.mark.severity("critical")
def test_alg_none_token_is_rejected(api):
    """Unsigned tokens (alg: none) are refused"""
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'security-officer', 'scope': 'audit:read', 'exp': int(time.time()) + 600})}."
    assert api.get("/v1/audit", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


@pytest.mark.req("REQ-HSM-02")
@pytest.mark.severity("high")
def test_token_signed_with_another_key_is_rejected(api):
    """A token signed with a guessed key is refused"""
    guessed = jwt.encode({"sub": "security-officer", "scope": "audit:read", "exp": int(time.time()) + 600}, "secret", algorithm="HS256")
    assert api.get("/v1/audit", headers={"Authorization": f"Bearer {guessed}"}).status_code == 401


@pytest.mark.req("REQ-HSM-12")
@pytest.mark.severity("medium")
@pytest.mark.defect("HSM-SEC-001")
@pytest.mark.xfail(strict=True, reason="HSM-SEC-001: no lockout after repeated failed client authentication")
def test_client_is_locked_after_repeated_failures(api):
    """Ten failed logins lock the client (brute-force protection)"""
    for _ in range(10):
        api.post("/v1/auth/token", json={"client_id": "card-issuing", "client_secret": "wrong"})
    locked = api.post("/v1/auth/token", json={"client_id": "card-issuing", "client_secret": "issuing-demo-secret"})
    assert locked.status_code in (423, 429), "the correct secret still works after 10 failures"
