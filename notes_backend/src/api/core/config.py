"""
Centralized configuration for the Notes backend.

All configuration is loaded from environment variables (optionally via .env),
so deployment can inject the correct values without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from .env if present (development convenience).
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    postgres_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 60 * 24 * 7  # 7 days by default


def _require_env(name: str) -> str:
    """Return the value of a required environment variable or raise a ValueError."""
    value = os.getenv(name)
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            "Please configure it in the deployment environment."
        )
    return value


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Get application Settings.

    Returns:
        Settings: Resolved configuration.
    """
    # We prefer POSTGRES_URL because it fully specifies host/port/db.
    # The orchestrator for the database container is expected to provide it.
    postgres_url = _require_env("POSTGRES_URL")

    # JWT secret is required in any environment (including dev) to avoid insecure defaults.
    jwt_secret_key = _require_env("JWT_SECRET_KEY")

    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    exp_minutes_raw = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    if exp_minutes_raw:
        try:
            exp_minutes = int(exp_minutes_raw)
        except ValueError as exc:
            raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from exc
    else:
        exp_minutes = 60 * 24 * 7

    return Settings(
        postgres_url=postgres_url,
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=jwt_algorithm,
        access_token_exp_minutes=exp_minutes,
    )
