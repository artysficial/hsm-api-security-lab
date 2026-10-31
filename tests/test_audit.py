"""Audit logging: sensitive operations are traceable, without sensitive data in the log."""

import json

import pytest

pytestmark = pytest.mark.category("Audit logging")


@pytest.mark.req("REQ-HSM-10")
@pytest.mark.severity("high")
def test_sensitive_operations_are_audited(api, auth, new_key):
    """Key generation, PIN translation and MAC operations each leave an audit entry"""
    source, destination, tak = new_key("payments-switch", "ZPK"), new_key("payments-switch", "ZPK"), new_key("payments-switch", "TAK")
    api.post("/v1/pin/translate", json={"pin_block": "0412AC89EF5B3D7A", "format": "ISO-0", "source_key_id": source["id"], "destination_key_id": destination["id"]}, headers=auth("payments-switch"))
    api.post("/v1/mac/generate", json={"key_id": tak["id"], "data": "ABCD"}, headers=auth("payments-switch"))

    entries = api.get("/v1/audit?limit=500", headers=auth("security-officer")).json()["entries"]
    actions = {(e["action"], e["key_id"]) for e in entries if e["client"] == "payments-switch"}
    assert ("key.generate", tak["id"]) in actions
    assert ("pin.translate", source["id"]) in actions
    assert ("mac.generate", tak["id"]) in actions
    assert all({"at", "client", "action", "key_id", "outcome"} <= set(e) for e in entries)


@pytest.mark.req("REQ-HSM-10")
@pytest.mark.severity("critical")
def test_audit_log_contains_no_pin_blocks_or_message_data(api, auth, new_key):
    """PIN blocks and MAC input never appear in the audit log"""
    source, destination = new_key("payments-switch", "ZPK"), new_key("payments-switch", "ZPK")
    pin_block, data = "0412AC89EF5B3D7A", "DEADBEEF00112233"
    api.post("/v1/pin/translate", json={"pin_block": pin_block, "format": "ISO-0", "source_key_id": source["id"], "destination_key_id": destination["id"]}, headers=auth("payments-switch"))
    tak = new_key("payments-switch", "TAK")
    api.post("/v1/mac/generate", json={"key_id": tak["id"], "data": data}, headers=auth("payments-switch"))
    log = json.dumps(api.get("/v1/audit?limit=500", headers=auth("security-officer")).json())
    assert pin_block not in log and data not in log


@pytest.mark.req("REQ-HSM-06", "REQ-HSM-10")
@pytest.mark.severity("medium")
def test_refused_operations_are_audited(api, auth, new_key):
    """Key-usage violations are logged as refused"""
    zpk = new_key("payments-switch", "ZPK")
    api.post("/v1/mac/generate", json={"key_id": zpk["id"], "data": "00"}, headers=auth("payments-switch"))
    entries = api.get("/v1/audit?limit=500", headers=auth("security-officer")).json()["entries"]
    assert any(e["key_id"] == zpk["id"] and e["outcome"].startswith("refused") for e in entries)
