"""
Security utilities: password hashing and JWT token encode/decode.

This implementation intentionally avoids extra dependencies. It uses PBKDF2-HMAC
for password hashing and HS256 for JWT (via PyJWT is NOT used to avoid adding deps).
Instead, we implement minimal JWT creation/verification using standard library.

NOTE: This is sufficient for a template/demo project. For production:
- Prefer a hardened JWT library (e.g., PyJWT)
- Consider rotating keys and refresh tokens
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.api.core.config import get_settings


@dataclass(frozen=True)
class TokenData:
    """Decoded JWT claims we care about."""

    sub: str
    email: str
    exp: int


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Returns a string of the form: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    if not password:
        raise ValueError("Password must not be empty")

    iterations = 200_000
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(dk)}"


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        scheme, iterations_str, salt_b64, hash_b64 = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _jwt_sign(message: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


# PUBLIC_INTERFACE
def create_access_token(*, user_id: str, email: str) -> Dict[str, Any]:
    """Create a signed JWT access token for a user.

    Returns:
        dict: { "access_token": str, "token_type": "bearer", "expires_at": int }
    """
    settings = get_settings()
    now = int(time.time())
    exp = now + settings.access_token_exp_minutes * 60

    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {"sub": user_id, "email": email, "iat": now, "exp": exp}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = _jwt_sign(signing_input, settings.jwt_secret_key)
    token = f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"

    return {"access_token": token, "token_type": "bearer", "expires_at": exp}


# PUBLIC_INTERFACE
def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and verify an access token.

    Returns:
        TokenData | None: Token data if valid, else None.
    """
    settings = get_settings()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = _b64url_decode(signature_b64)

        expected = _jwt_sign(signing_input, settings.jwt_secret_key)
        if not hmac.compare_digest(signature, expected):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            return None

        sub = str(payload.get("sub", ""))
        email = str(payload.get("email", ""))
        if not sub or not email:
            return None

        return TokenData(sub=sub, email=email, exp=exp)
    except Exception:
        return None
