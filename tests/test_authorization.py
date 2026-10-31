"""OWASP API1:2023 BOLA and API5:2023 Broken Function Level Authorization."""

import pytest


@pytest.mark.category("API1 BOLA")
@pytest.mark.req("REQ-HSM-04")
@pytest.mark.severity("critical")
def test_client_cannot_read_another_clients_key(api, auth, new_key):
    """A client cannot read a key owned by another client"""
    key = new_key("payments-switch", "ZPK")
    assert api.get(f"/v1/keys/{key['id']}", headers=auth("payments-switch")).status_code == 200
    assert api.get(f"/v1/keys/{key['id']}", headers=auth("card-issuing")).status_code == 404


@pytest.mark.category("API1 BOLA")
@pytest.mark.req("REQ-HSM-04")
@pytest.mark.severity("high")
def test_foreign_and_missing_keys_look_identical(api, auth, new_key):
    """Someone else's key and a non-existent key return the same response (no enumeration)"""
    foreign = new_key("payments-switch", "TAK")
    a = api.get(f"/v1/keys/{foreign['id']}", headers=auth("card-issuing"))
    b = api.get("/v1/keys/key_ffffffffffffffff", headers=auth("card-issuing"))
    assert (a.status_code, a.json()) == (b.status_code, b.json())


@pytest.mark.category("API1 BOLA")
@pytest.mark.req("REQ-HSM-04")
@pytest.mark.severity("critical")
def test_client_cannot_use_another_clients_key_for_crypto(api, auth, new_key):
    """A client cannot MAC with a key it does not own"""
    foreign = new_key("payments-switch", "TAK")
    response = api.post("/v1/mac/generate", json={"key_id": foreign["id"], "data": "00112233"}, headers=auth("card-issuing"))
    assert response.status_code == 404


@pytest.mark.category("API5 Function level authorization")
@pytest.mark.req("REQ-HSM-03")
@pytest.mark.severity("high")
@pytest.mark.parametrize("client_id, method, path, body", [
    ("security-officer", "POST", "/v1/keys", {"type": "ZPK"}),
    ("card-issuing", "POST", "/v1/pin/translate", {"pin_block": "0412AC89EF5B3D7A", "format": "ISO-0", "source_key_id": "x", "destination_key_id": "y"}),
    ("payments-switch", "GET", "/v1/audit", None),
    ("card-issuing", "GET", "/v1/audit", None),
])
def test_scopes_limit_what_each_client_can_do(api, auth, client_id, method, path, body):
    """Clients are refused operations outside their scopes (least privilege)"""
    response = api.request(method, path, json=body, headers=auth(client_id))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_scope"


@pytest.mark.category("API5 Function level authorization")
@pytest.mark.req("REQ-HSM-03", "REQ-HSM-10")
@pytest.mark.severity("medium")
def test_security_officer_can_read_the_audit_log(api, auth):
    """The security officer role can read the audit log"""
    response = api.get("/v1/audit", headers=auth("security-officer"))
    assert response.status_code == 200
    assert isinstance(response.json()["entries"], list)
