"""Injection and error handling: hostile input is rejected without leaking internals."""

import pytest

pytestmark = pytest.mark.category("Injection & error handling")

PAYLOADS = ["' OR '1'='1", "key_1; DROP TABLE keys--", "../../etc/passwd", "%2e%2e%2fadmin", "<script>alert(1)</script>", "${jndi:ldap://x/a}"]
LEAKS = ["Traceback", "File \"", "pydantic", "sqlalchemy", "uvicorn", "Exception", "line "]


@pytest.mark.req("REQ-HSM-09")
@pytest.mark.severity("high")
@pytest.mark.parametrize("payload", PAYLOADS)
def test_hostile_key_ids_are_rejected_quietly(api, auth, payload):
    """Injection and traversal payloads in a key id return a plain 404"""
    response = api.get(f"/v1/keys/{payload}", headers=auth("payments-switch"))
    assert response.status_code == 404
    assert payload not in response.text


@pytest.mark.req("REQ-HSM-09")
@pytest.mark.severity("medium")
@pytest.mark.parametrize("payload", PAYLOADS)
def test_hostile_labels_are_rejected_and_not_reflected(api, auth, payload):
    """Hostile key labels fail validation and are not echoed back"""
    response = api.post("/v1/keys", json={"type": "ZPK", "label": payload}, headers=auth("payments-switch"))
    assert response.status_code == 422
    assert payload not in response.text


@pytest.mark.req("REQ-HSM-09")
@pytest.mark.severity("medium")
def test_malformed_json_gets_a_generic_error(api, auth):
    """Broken JSON returns a structured 4xx without stack traces"""
    response = api.post("/v1/keys", content=b'{"type": "ZPK"', headers={**auth("payments-switch"), "Content-Type": "application/json"})
    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert not any(leak in response.text for leak in LEAKS)


@pytest.mark.req("REQ-HSM-09")
@pytest.mark.severity("medium")
def test_non_hex_mac_data_is_rejected(api, auth, new_key):
    """MAC input must be hex; anything else is refused"""
    tak = new_key("card-issuing", "TAK")
    response = api.post("/v1/mac/generate", json={"key_id": tak["id"], "data": "not-hex!"}, headers=auth("card-issuing"))
    assert response.status_code == 422
    assert not any(leak in response.text for leak in LEAKS)
