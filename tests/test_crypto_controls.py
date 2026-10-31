"""Payment-HSM business controls: key usage enforcement, PIN blocks and MAC integrity."""

import pytest

pytestmark = pytest.mark.category("Cryptographic controls")


@pytest.mark.req("REQ-HSM-06")
@pytest.mark.severity("critical")
def test_mac_key_cannot_translate_pins(api, auth, new_key):
    """A MAC key (TAK) is refused for PIN translation"""
    zpk, tak = new_key("payments-switch", "ZPK"), new_key("payments-switch", "TAK")
    body = {"pin_block": "0412AC89EF5B3D7A", "format": "ISO-0", "source_key_id": tak["id"], "destination_key_id": zpk["id"]}
    response = api.post("/v1/pin/translate", json=body, headers=auth("payments-switch"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "key_usage_violation"


@pytest.mark.req("REQ-HSM-06")
@pytest.mark.severity("critical")
@pytest.mark.parametrize("key_type", ["ZPK", "ZMK"])
def test_non_mac_keys_cannot_generate_macs(api, auth, new_key, key_type):
    """PIN and key-encryption keys are refused for MAC generation"""
    key = new_key("payments-switch", key_type)
    response = api.post("/v1/mac/generate", json={"key_id": key["id"], "data": "00112233"}, headers=auth("payments-switch"))
    assert response.status_code == 409


@pytest.mark.req("REQ-HSM-07")
@pytest.mark.severity("high")
@pytest.mark.parametrize("fmt, pin_block", [("ISO-0", "0412AC89EF5B3D7A"), ("ISO-4", "4412345FFFFFFFFF0123456789ABCDEF")])
def test_pin_translation_is_deterministic_and_changes_the_block(api, auth, new_key, fmt, pin_block):
    """PIN translation returns a same-length block under the destination key, consistently"""
    source, destination = new_key("payments-switch", "ZPK"), new_key("payments-switch", "ZPK")
    body = {"pin_block": pin_block, "format": fmt, "source_key_id": source["id"], "destination_key_id": destination["id"]}
    first = api.post("/v1/pin/translate", json=body, headers=auth("payments-switch")).json()
    second = api.post("/v1/pin/translate", json=body, headers=auth("payments-switch")).json()
    assert first["pin_block"] == second["pin_block"]
    assert len(first["pin_block"]) == len(pin_block) and first["pin_block"] != pin_block.upper()


@pytest.mark.req("REQ-HSM-07", "REQ-HSM-09")
@pytest.mark.severity("high")
@pytest.mark.parametrize("fmt, pin_block", [("ISO-0", "0412AC89EF5B3D7"), ("ISO-0", "0412AC89EF5B3D7Z"), ("ISO-4", "0412AC89EF5B3D7A")])
def test_malformed_pin_blocks_are_rejected(api, auth, new_key, fmt, pin_block):
    """PIN blocks of the wrong length or with non-hex characters are rejected"""
    source, destination = new_key("payments-switch", "ZPK"), new_key("payments-switch", "ZPK")
    body = {"pin_block": pin_block, "format": fmt, "source_key_id": source["id"], "destination_key_id": destination["id"]}
    response = api.post("/v1/pin/translate", json=body, headers=auth("payments-switch"))
    assert response.status_code == 422
    assert pin_block not in response.text


@pytest.mark.req("REQ-HSM-08")
@pytest.mark.severity("critical")
def test_mac_detects_tampered_data(api, auth, new_key):
    """A MAC verifies for the original message and fails when one byte changes"""
    tak = new_key("card-issuing", "TAK")
    message = "0200B238000102C0800004000000000000010000"
    mac = api.post("/v1/mac/generate", json={"key_id": tak["id"], "data": message}, headers=auth("card-issuing")).json()["mac"]
    verify = lambda data: api.post("/v1/mac/verify", json={"key_id": tak["id"], "data": data, "mac": mac}, headers=auth("card-issuing")).json()["valid"]
    assert verify(message) is True
    assert verify(message[:-2] + "01") is False


@pytest.mark.req("REQ-HSM-08")
@pytest.mark.severity("high")
def test_mac_from_another_key_does_not_verify(api, auth, new_key):
    """A MAC made with one key does not verify under another"""
    a, b = new_key("card-issuing", "TAK"), new_key("card-issuing", "TAK")
    mac = api.post("/v1/mac/generate", json={"key_id": a["id"], "data": "CAFEBABE"}, headers=auth("card-issuing")).json()["mac"]
    response = api.post("/v1/mac/verify", json={"key_id": b["id"], "data": "CAFEBABE", "mac": mac}, headers=auth("card-issuing"))
    assert response.json()["valid"] is False
