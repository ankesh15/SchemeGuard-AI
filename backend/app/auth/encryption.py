"""Authenticated encryption with owner/purpose binding to prevent record swapping."""

import json
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import Settings


def cipher(settings: Settings) -> Fernet:
    if not settings.profile_encryption_key:
        raise HTTPException(503, "Private profile storage is not configured")
    return Fernet(settings.profile_encryption_key.get_secret_value().encode())


def seal(settings: Settings, user_id: UUID, purpose: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {"owner": str(user_id), "purpose": purpose, "data": payload},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return cipher(settings).encrypt(raw).decode()


def unseal(settings: Settings, user_id: UUID, purpose: str, token: str) -> dict[str, Any]:
    try:
        value = json.loads(cipher(settings).decrypt(token.encode()))
        if (
            value["owner"] != str(user_id)
            or value["purpose"] != purpose
            or not isinstance(value["data"], dict)
        ):
            raise ValueError("Invalid private record binding")
        return value["data"]
    except (InvalidToken, ValueError, KeyError, TypeError) as error:
        raise HTTPException(
            503, "Private record could not be decrypted safely; restore its configured key"
        ) from error
