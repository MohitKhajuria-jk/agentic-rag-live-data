"""Encrypts OAuth tokens before they are written to the database."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def load_or_create_secret(configured: str, data_dir: Path) -> str:
    if configured:
        return configured
    path = data_dir / ".secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    path.write_text(secret, encoding="utf-8")
    return secret


class TokenVault:
    """Fernet (AES-128-CBC + HMAC) encryption keyed from the app secret."""

    def __init__(self, secret: str):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def seal(self, data: dict[str, Any]) -> bytes:
        return self._fernet.encrypt(json.dumps(data).encode("utf-8"))

    def open(self, blob: bytes) -> dict[str, Any] | None:
        try:
            return json.loads(self._fernet.decrypt(blob))
        except (InvalidToken, ValueError):
            return None
