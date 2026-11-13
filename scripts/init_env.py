"""Create a local .env once, without printing or hardcoding a password."""

import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print("Preserved existing .env")
else:
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace("replace-with-a-random-local-password", secrets.token_urlsafe(32))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(content)
    path.chmod(0o600)
    print("Created .env with a generated local database password")

# Add a stable private-storage key when upgrading an existing local environment.
# Never regenerate a present key: old private records depend on it.
existing = path.read_text(encoding="utf-8")
if not any(line.startswith("PROFILE_ENCRYPTION_KEY=") and line.partition("=")[2].strip() for line in existing.splitlines()):
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    with path.open("a", encoding="utf-8") as file:
        file.write("\nPROFILE_ENCRYPTION_KEY=" + key + "\n")
    path.chmod(0o600)
    print("Configured private-storage encryption without displaying the key")
