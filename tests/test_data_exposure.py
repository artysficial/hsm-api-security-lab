"""OWASP API3:2023 Broken Object Property Level Authorization (data exposure, mass assignment)."""

import pytest

pytestmark = pytest.mark.category("API3 Property level authorization")

FORBIDDEN_FIELDS = {"secret", "clear_key", "key", "plaintext", "owner", "lmk"}


@pytest.mark.req("REQ-HSM-05")
@pytest.mark.severity("critical")
@pytest.mark.parametrize("key_type", ["ZPK", "PVK", "TAK", "ZMK"])
def test_clear_key_material_is_never_returned(api, auth, new_key, key_type):
    """Key responses contain metadata and a wrapped key block only, never clear key material"""
    created = new_key("payments-switch", key_type)
    fetched = api.get(f"/v1/keys/{created['id']}", headers=auth("payments-switch")).json()
    for body in (created, fetched):
        assert not FORBIDDEN_FIELDS & set(body), f"exposed: {FORBIDDEN_FIELDS & set(body)}"
        assert set(body) == {"id", "type", "usage", "algorithm", "label", "kcv", "key_block", "created_at"}


@pytest.mark.req("REQ-HSM-04", "REQ-HSM-06")
@pytest.mark.severity("high")
@pytest.mark.parametrize("extra", [{"owner": "card-issuing"}, {"usage": "mac"}, {"exportable": True}])
def test_protected_properties_cannot_be_mass_assigned(api, auth, extra):
    """Owner, usage and exportability cannot be set by the caller"""
    response = api.post("/v1/keys", json={"type": "ZPK", **extra}, headers=auth("payments-switch"))
    assert response.status_code == 422


@pytest.mark.req("REQ-HSM-05")
@pytest.mark.severity("medium")
def test_key_check_value_is_six_hex_characters(new_key):
    """The key check value (KCV) is 6 hex characters, enough to verify a key without exposing it"""
    kcv = new_key("payments-switch", "ZPK")["kcv"]
    assert len(kcv) == 6 and all(c in "0123456789ABCDEF" for c in kcv)
