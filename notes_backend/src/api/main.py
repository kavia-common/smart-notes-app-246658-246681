"""
FastAPI application entrypoint for Smart Notes.

This backend provides:
- Authentication (JWT bearer)
- Notes CRUD + search
- Tags CRUD
- User settings (theme)
- Offline-first sync (pull/push)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.core.config import get_settings
from src.api.core.database import init_db
from src.api.routers import auth, notes, settings, sync, tags

openapi_tags = [
    {"name": "health", "description": "Service health and diagnostics."},
    {"name": "auth", "description": "User registration, login, and session identity."},
    {"name": "notes", "description": "Create, update, delete, and search notes."},
    {"name": "tags", "description": "Manage tags and organize notes."},
    {"name": "settings", "description": "User preferences such as theme."},
    {"name": "sync", "description": "Offline-first synchronization endpoints."},
]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema at startup.

    Note: startup should not fail hard in preview/dev environments if DB init fails
    transiently; we log the error and allow health endpoints to come up.
    """
    try:
        init_db()
    except Exception:
        logger.exception("Database initialization failed at startup; continuing without blocking server startup.")
    yield


app = FastAPI(
    title="Smart Notes Backend API",
    description="REST API for Smart Notes (auth, notes, tags, settings, and sync).",
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

_settings = get_settings()
_allow_origins = _settings.allowed_origins or ["*"]

# Starlette does not allow allow_credentials=True with wildcard origins.
_allow_credentials = "*" not in _allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=_settings.allowed_methods or ["*"],
    allow_headers=_settings.allowed_headers or ["*"],
    max_age=_settings.cors_max_age,
)


def _validation_error_message(exc: RequestValidationError) -> str:
    """Convert FastAPI validation error structure into a stable string detail."""
    try:
        errors = exc.errors()
        if not errors:
            return "Validation error."
        first = errors[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = str(first.get("msg", "Invalid request"))
        return f"{loc}: {msg}".strip(": ").strip() if loc else msg
    except Exception:
        return "Validation error."


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure validation errors match ErrorResponse shape: { "detail": "<string>" }."""
    _ = request
    return JSONResponse(status_code=422, content={"detail": _validation_error_message(exc)})


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Simple health check endpoint.",
    operation_id="health_check",
)
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint.

    Returns:
        dict: { "message": "Healthy" }
    """
    return {"message": "Healthy"}


@app.get(
    "/healthz",
    tags=["health"],
    summary="Health check (healthz)",
    description="Health check endpoint used by infrastructure probes.",
    operation_id="health_check_healthz",
)
# PUBLIC_INTERFACE
def health_check_healthz():
    """Health check endpoint (healthz).

    Returns:
        dict: { "message": "Healthy" }
    """
    return {"message": "Healthy"}


# Routers
app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(tags.router)
app.include_router(settings.router)
app.include_router(sync.router)
