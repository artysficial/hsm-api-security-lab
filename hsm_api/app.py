"""Simulated payment HSM REST API (system under test).

Modelled on the command families of real payment HSMs (key generation, PIN translation, MAC),
exposed over REST the way banks increasingly front their HSMs. The cryptography is simulated
with HMAC so the lab runs anywhere; the *security behaviour* (authentication, scopes, key
ownership, key usage, validation, audit, rate limits, headers) is what is under test.

Two weaknesses are seeded on purpose so the suite has real findings to report:
  HSM-SEC-001  no lockout after repeated failed client authentications (REQ-HSM-12)
  HSM-SEC-002  Strict-Transport-Security header missing (REQ-HSM-13)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from typing import Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from . import config

app = FastAPI(title="Simulated Payment HSM API", version="1.0.0", docs_url="/docs", redoc_url=None)
bearer = HTTPBearer(auto_error=False)

HEX = re.compile(r"^[0-9A-Fa-f]+$")
KEY_USAGE = {"ZPK": "pin", "PVK": "pin", "TAK": "mac", "ZMK": "kek"}

keys: dict[str, dict] = {}
audit_log: list[dict] = []
_calls: dict[str, deque] = defaultdict(deque)


# ---- errors: one shape, never internal detail or echoed input (REQ-HSM-09)

def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    code, message = exc.detail if isinstance(exc.detail, tuple) else ("error", str(exc.detail))
    response = error(exc.status_code, code, message)
    if exc.status_code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # field names only: pydantic's default response would reflect the submitted values
    fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors()})
    return error(422, "invalid_request", f"Invalid or missing fields: {', '.join(fields)}")


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    return error(500, "internal_error", "The request could not be processed")


# ---- transport hardening (REQ-HSM-13, REQ-HSM-14)

@app.middleware("http")
async def hardening(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > config.MAX_BODY_BYTES:
        return error(413, "payload_too_large", f"Request body exceeds {config.MAX_BODY_BYTES} bytes")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # HSM-SEC-002 (seeded): Strict-Transport-Security is never set
    return response


# ---- authentication and authorisation (REQ-HSM-01..03)

class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(max_length=64)
    client_secret: str = Field(max_length=128)


@app.post("/v1/auth/token")
def issue_token(body: TokenRequest):
    client = config.CLIENTS.get(body.client_id)
    valid = client is not None and hmac.compare_digest(client["secret"], body.client_secret)
    # HSM-SEC-001 (seeded): failures are not counted, so there is no lockout
    if not valid:
        raise HTTPException(401, ("invalid_client", "Client authentication failed"))
    now = int(time.time())
    token = jwt.encode(
        {"sub": body.client_id, "scope": " ".join(client["scopes"]), "iat": now, "exp": now + config.TOKEN_TTL, "jti": uuid.uuid4().hex},
        config.SIGNING_KEY,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "Bearer", "expires_in": config.TOKEN_TTL, "scope": " ".join(client["scopes"])}


def caller(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, ("unauthorized", "A bearer token is required"))
    try:
        # algorithms is pinned: tokens claiming "none" or another algorithm are rejected
        claims = jwt.decode(credentials.credentials, config.SIGNING_KEY, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(401, ("invalid_token", "The token is invalid or expired"))
    return {"client": claims["sub"], "scopes": set(claims.get("scope", "").split())}


def require(scope: str):
    def check(who: dict = Depends(caller)) -> dict:
        if scope not in who["scopes"]:
            raise HTTPException(403, ("insufficient_scope", f"This operation requires the {scope} scope"))
        return who
    return check


def rate_limited(who: dict) -> None:
    window = _calls[who["client"]]
    now = time.monotonic()
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, ("rate_limited", "Too many cryptographic operations; slow down"))
    window.append(now)


def audit(who: dict, action: str, key_id: str | None, outcome: str) -> None:
    # never log PIN blocks, MAC data or key material (REQ-HSM-10)
    audit_log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "client": who["client"], "action": action, "key_id": key_id, "outcome": outcome})


# ---- keys (REQ-HSM-04..06)

class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # no mass assignment of owner/exportable/usage
    type: Literal["ZPK", "PVK", "TAK", "ZMK"]
    algorithm: Literal["AES-256", "TDES-3K"] = "AES-256"
    label: str = Field(default="", max_length=64, pattern=r"^[\w .-]*$")


def public(key: dict) -> dict:
    return {k: key[k] for k in ("id", "type", "usage", "algorithm", "label", "kcv", "key_block", "created_at")}


def own_key(key_id: str, who: dict) -> dict:
    key = keys.get(key_id)
    # 404 rather than 403, so other clients' key ids cannot be confirmed
    if key is None or key["owner"] != who["client"]:
        raise HTTPException(404, ("not_found", "Key not found"))
    return key


@app.post("/v1/keys", status_code=201)
def generate_key(body: KeyCreate, who: dict = Depends(require("keys:generate"))):
    secret = secrets.token_bytes(32)
    key_id = f"key_{uuid.uuid4().hex[:16]}"
    kcv = hmac.new(secret, b"\x00" * 16, hashlib.sha256).hexdigest()[:6].upper()
    wrapped = hmac.new(config.LMK, secret, hashlib.sha256).hexdigest().upper()
    keys[key_id] = {
        "id": key_id, "owner": who["client"], "type": body.type, "usage": KEY_USAGE[body.type], "algorithm": body.algorithm,
        "label": body.label, "kcv": kcv, "key_block": f"D0144{body.type[0]}0AE00E0000{wrapped}", "secret": secret,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    audit(who, "key.generate", key_id, "success")
    return public(keys[key_id])


@app.get("/v1/keys/{key_id}")
def get_key(key_id: str, who: dict = Depends(require("keys:read"))):
    if not re.fullmatch(r"key_[0-9a-f]{16}", key_id):
        raise HTTPException(404, ("not_found", "Key not found"))
    return public(own_key(key_id, who))


# ---- PIN translation (REQ-HSM-06, REQ-HSM-07)

PIN_BLOCK_LENGTH = {"ISO-0": 16, "ISO-4": 32}


class PinTranslate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin_block: str = Field(min_length=16, max_length=32)
    format: Literal["ISO-0", "ISO-4"]
    source_key_id: str = Field(max_length=32)
    destination_key_id: str = Field(max_length=32)


@app.post("/v1/pin/translate")
def translate_pin(body: PinTranslate, who: dict = Depends(require("pin:translate"))):
    rate_limited(who)
    if len(body.pin_block) != PIN_BLOCK_LENGTH[body.format] or not HEX.match(body.pin_block):
        raise HTTPException(422, ("invalid_pin_block", f"A {body.format} PIN block is {PIN_BLOCK_LENGTH[body.format]} hex characters"))
    source, destination = own_key(body.source_key_id, who), own_key(body.destination_key_id, who)
    if source["usage"] != "pin" or destination["usage"] != "pin":
        audit(who, "pin.translate", body.source_key_id, "refused: key usage")
        raise HTTPException(409, ("key_usage_violation", "Both keys must be PIN keys"))
    inner = hmac.new(source["secret"], bytes.fromhex(body.pin_block), hashlib.sha256).digest()
    translated = hmac.new(destination["secret"], inner, hashlib.sha256).hexdigest()[: len(body.pin_block)].upper()
    audit(who, "pin.translate", body.source_key_id, "success")
    return {"pin_block": translated, "format": body.format, "key_id": destination["id"]}


# ---- MAC (REQ-HSM-06, REQ-HSM-08)

class MacRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str = Field(max_length=32)
    data: str = Field(min_length=2, max_length=8192)
    mac: str | None = Field(default=None, max_length=64)


def compute_mac(key: dict, data: str) -> str:
    if not HEX.match(data) or len(data) % 2:
        raise HTTPException(422, ("invalid_data", "data must be an even-length hex string"))
    return hmac.new(key["secret"], bytes.fromhex(data), hashlib.sha256).hexdigest()[:16].upper()


def mac_key(key_id: str, who: dict) -> dict:
    key = own_key(key_id, who)
    if key["usage"] != "mac":
        audit(who, "mac", key_id, "refused: key usage")
        raise HTTPException(409, ("key_usage_violation", "The key is not a MAC key"))
    return key


@app.post("/v1/mac/generate")
def generate_mac(body: MacRequest, who: dict = Depends(require("mac:generate"))):
    rate_limited(who)
    mac = compute_mac(mac_key(body.key_id, who), body.data)
    audit(who, "mac.generate", body.key_id, "success")
    return {"mac": mac, "key_id": body.key_id}


@app.post("/v1/mac/verify")
def verify_mac(body: MacRequest, who: dict = Depends(require("mac:verify"))):
    rate_limited(who)
    if not body.mac:
        raise HTTPException(422, ("invalid_request", "Invalid or missing fields: mac"))
    valid = hmac.compare_digest(compute_mac(mac_key(body.key_id, who), body.data), body.mac.upper())
    audit(who, "mac.verify", body.key_id, "valid" if valid else "invalid")
    return {"valid": valid}


# ---- audit (REQ-HSM-10)

@app.get("/v1/audit")
def read_audit(limit: int = 100, who: dict = Depends(require("audit:read"))):
    return {"entries": audit_log[-max(1, min(limit, 500)):]}


@app.get("/health")
def health():
    return {"status": "ok"}


def run() -> None:  # python -m hsm_api
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8443)), server_header=False)
