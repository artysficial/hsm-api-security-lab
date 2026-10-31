"""Lab configuration. Demo credentials only: this simulated HSM holds no real keys."""

import os

SIGNING_KEY = os.environ.get("HSM_SIGNING_KEY", "lab-signing-key-not-for-production-use-0123456789")
LMK = os.environ.get("HSM_LMK", "lab-local-master-key").encode()
TOKEN_TTL = int(os.environ.get("HSM_TOKEN_TTL", 900))  # 15 minutes (REQ-HSM-01)
RATE_LIMIT_PER_MINUTE = int(os.environ.get("HSM_RATE_LIMIT", 60))  # REQ-HSM-11
MAX_BODY_BYTES = 16 * 1024  # REQ-HSM-14

# least privilege: each client gets only the scopes its role needs (REQ-HSM-03)
CLIENTS = {
    "payments-switch": {"secret": "switch-demo-secret", "scopes": ["keys:generate", "keys:read", "pin:translate", "mac:generate", "mac:verify"]},
    "card-issuing": {"secret": "issuing-demo-secret", "scopes": ["keys:generate", "keys:read", "mac:generate", "mac:verify"]},
    "security-officer": {"secret": "officer-demo-secret", "scopes": ["audit:read", "keys:read"]},
}
