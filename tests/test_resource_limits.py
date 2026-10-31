"""OWASP API4:2023 Unrestricted Resource Consumption."""

import pytest

from hsm_api import config

pytestmark = pytest.mark.category("API4 Resource consumption")


@pytest.mark.req("REQ-HSM-11")
@pytest.mark.severity("high")
def test_cryptographic_calls_are_rate_limited(api, auth, new_key):
    """MAC generation is throttled once the per-minute limit is reached"""
    tak = new_key("card-issuing", "TAK")
    statuses = [
        api.post("/v1/mac/generate", json={"key_id": tak["id"], "data": "00"}, headers=auth("card-issuing")).status_code
        for _ in range(config.RATE_LIMIT_PER_MINUTE + 3)
    ]
    assert statuses[: config.RATE_LIMIT_PER_MINUTE] == [200] * config.RATE_LIMIT_PER_MINUTE
    assert statuses[-1] == 429


@pytest.mark.req("REQ-HSM-14")
@pytest.mark.severity("medium")
def test_oversized_bodies_are_rejected(api, auth):
    """Request bodies over 16 KB are refused with 413"""
    body = '{"key_id": "key_0000000000000000", "data": "' + "00" * 9000 + '"}'
    response = api.post("/v1/mac/generate", content=body, headers={**auth("card-issuing"), "Content-Type": "application/json"})
    assert response.status_code == 413
