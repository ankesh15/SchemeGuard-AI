"""Create a local .env once, without printing or hardcoding a password."""

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
