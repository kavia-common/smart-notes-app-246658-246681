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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema at startup."""
    init_db()
    yield


app = FastAPI(
    title="Smart Notes Backend API",
    description="REST API for Smart Notes (auth, notes, tags, settings, and sync).",
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend container origin may vary per environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Routers
app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(tags.router)
app.include_router(settings.router)
app.include_router(sync.router)
