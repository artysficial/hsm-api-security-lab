"""Starts the simulated HSM on a real HTTP port, so the suite tests it over the wire
(headers, status codes, body limits) exactly as an external client would.
Set HSM_BASE_URL to point the same suite at another deployment."""

from __future__ import annotations

import os
import socket
import threading
import time

os.environ.setdefault("HSM_RATE_LIMIT", "25")  # small limit so the rate-limit test stays fast

import httpx
import pytest
import uvicorn

from hsm_api import app as hsm

pytest_plugins = ["results_plugin"]

SECRETS = {"payments-switch": "switch-demo-secret", "card-issuing": "issuing-demo-secret", "security-officer": "officer-demo-secret"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    if os.environ.get("HSM_BASE_URL"):
        yield os.environ["HSM_BASE_URL"].rstrip("/")
        return
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(hsm.app, host="127.0.0.1", port=port, log_level="warning", server_header=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def api(base_url):
    with httpx.Client(base_url=base_url, timeout=10) as client:
        yield client


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    # white-box: each test starts with an empty rate-limit window (in-process server only)
    hsm._calls.clear()


@pytest.fixture(scope="session")
def token(api):
    cache: dict[str, str] = {}

    def get(client_id: str) -> str:
        if client_id not in cache:
            response = api.post("/v1/auth/token", json={"client_id": client_id, "client_secret": SECRETS[client_id]})
            assert response.status_code == 200, response.text
            cache[client_id] = response.json()["access_token"]
        return cache[client_id]

    return get


@pytest.fixture
def auth(token):
    return lambda client_id: {"Authorization": f"Bearer {token(client_id)}"}


@pytest.fixture
def new_key(api, auth):
    def create(client_id: str, key_type: str, label: str = "lab") -> dict:
        response = api.post("/v1/keys", json={"type": key_type, "label": label}, headers=auth(client_id))
        assert response.status_code == 201, response.text
        return response.json()

    return create
