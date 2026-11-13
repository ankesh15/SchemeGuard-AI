"""Create private credentials for an isolated local production-profile test, preserving existing files."""

import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".local/phase7-production.env"
path.parent.mkdir(mode=0o700, exist_ok=True)
if path.exists():
    print("Preserved existing local production-verification environment")
else:
    values = {
        "POSTGRES_DB": "schemeguard",
        "POSTGRES_OWNER": "phase7_owner",
        "POSTGRES_OWNER_PASSWORD": secrets.token_urlsafe(32),
        "POSTGRES_USER": "phase7_app",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "PROFILE_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "ADMIN_ALLOWED_ORIGINS": '["https://localhost:13443"]',
        "ALLOWED_HOSTS": '["api","localhost","127.0.0.1"]',
        "DOCUMENT_STORAGE_BACKEND": "filesystem",
        "ALLOW_LOCAL_DOCUMENT_STORAGE": "true",
        "PRODUCTION_API_PORT": "18000",
        "PRODUCTION_FRONTEND_PORT": "13000",
        "POSTGRES_VOLUME_NAME": "schemeguard-phase7-verification-postgres",
        "REDIS_VOLUME_NAME": "schemeguard-phase7-verification-redis",
        "DOCUMENT_VOLUME_NAME": "schemeguard-phase7-verification-documents",
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("\n".join(key + "=" + value for key, value in values.items()) + "\n")
    print("Created isolated local production-test configuration; no credentials printed")
