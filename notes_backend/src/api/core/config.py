"""
Centralized configuration for the Notes backend.

All configuration is loaded from environment variables (optionally via .env),
so deployment can inject the correct values without code changes.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache

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
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    allowed_headers: list[str] = field(default_factory=lambda: ["*"])
    allowed_methods: list[str] = field(default_factory=lambda: ["*"])
    cors_max_age: int = 3600


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
def build_postgres_url_from_parts() -> str:
    """Build a postgres URL from POSTGRES_* environment variables.

    This supports deployments where the orchestrator provides split DB vars
    (POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB/POSTGRES_PORT) instead of a full URL.

    Returns:
        str: SQLAlchemy-compatible PostgreSQL URL.
    """
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRES_PORT")
    host = os.getenv("POSTGRES_HOST", "localhost")

    missing = [k for k, v in [("POSTGRES_USER", user), ("POSTGRES_PASSWORD", password), ("POSTGRES_DB", db), ("POSTGRES_PORT", port)] if not v]
    if missing:
        raise ValueError(
            "Missing required database environment variables. "
            "Provide POSTGRES_URL or all of: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT. "
            f"Missing: {', '.join(missing)}"
        )

    # NOTE: Avoid logging/printing this value because it contains credentials.
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application Settings.

    Returns:
        Settings: Resolved configuration.
    """
    # Prefer POSTGRES_URL when provided; else build from split POSTGRES_* vars.
    postgres_url = os.getenv("POSTGRES_URL") or build_postgres_url_from_parts()

    # JWT secret: required for production, but allow a safe startup in preview/dev where
    # the orchestrator may not inject JWT_SECRET_KEY by generating an ephemeral key.
    #
    # SECURITY NOTE: This makes tokens invalid after a restart (acceptable for dev/preview).
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret_key:
        node_env = (os.getenv("NODE_ENV") or "development").lower()
        if node_env in {"production", "prod"}:
            jwt_secret_key = _require_env("JWT_SECRET_KEY")
        else:
            logging.getLogger(__name__).warning(
                "JWT_SECRET_KEY is not set; generating an ephemeral secret because NODE_ENV=%s. "
                "Set JWT_SECRET_KEY to make tokens stable across restarts.",
                node_env,
            )
            jwt_secret_key = secrets.token_urlsafe(48)

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
        allowed_origins=_csv_env("ALLOWED_ORIGINS", ["*"]),
        allowed_headers=_csv_env("ALLOWED_HEADERS", ["*"]),
        allowed_methods=_csv_env("ALLOWED_METHODS", ["*"]),
        cors_max_age=int(os.getenv("CORS_MAX_AGE", "3600") or "3600"),
    )
