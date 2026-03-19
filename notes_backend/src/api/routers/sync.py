"""
Synchronization routes.

These endpoints support a simple offline-first strategy:
- Clients store notes/tags locally.
- Clients call /sync/pull?since=<timestamp> to fetch server-side changes.
- Clients call /sync/push to upsert their local changes.
Conflict resolution: last-write-wins based on updated_at timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from src.api.core.deps import get_current_user, get_db
from src.api.models import Note, Tag, User, UserSettings
from src.api.schemas import (
    NoteResponse,
    SettingsResponse,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    TagResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    """Parse an RFC3339-ish timestamp from query string."""
    if not since:
        return None
    s = since.strip()
    # normalize Zulu
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid 'since' timestamp") from exc


@router.get(
    "/time",
    summary="Get server time",
    description="Returns the current server time (UTC). Useful for client sync alignment.",
    operation_id="sync_time",
)
# PUBLIC_INTERFACE
def get_server_time() -> dict:
    """Return current server time."""
    return {"server_time": _utcnow().isoformat()}


@router.get(
    "/pull",
    response_model=SyncPullResponse,
    summary="Pull changes",
    description="Fetch notes/tags/settings changed since a given timestamp.",
    operation_id="sync_pull",
)
# PUBLIC_INTERFACE
def pull_changes(
    since: Optional[str] = Query(None, description="ISO timestamp. Only return changes after this time."),
    include_deleted: bool = Query(True, description="Whether to include soft-deleted notes."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncPullResponse:
    """Pull changes since a timestamp."""
    since_dt = _parse_since(since)
    now = _utcnow()

    notes_q = (
        db.query(Note)
        .options(selectinload(Note.tags))
        .filter(Note.user_id == current_user.id)
    )
    tags_q = db.query(Tag).filter(Tag.user_id == current_user.id)

    if since_dt is not None:
        notes_q = notes_q.filter(Note.updated_at > since_dt)
        tags_q = tags_q.filter(Tag.updated_at > since_dt)

    if not include_deleted:
        notes_q = notes_q.filter(Note.deleted_at.is_(None))

    notes = notes_q.order_by(Note.updated_at.asc()).all()
    tags = tags_q.order_by(Tag.updated_at.asc()).all()

    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).one_or_none()
    settings_out: Optional[SettingsResponse] = None
    if settings is not None and (since_dt is None or settings.updated_at > since_dt):
        settings_out = SettingsResponse(theme=settings.theme, updated_at=settings.updated_at)

    return SyncPullResponse(
        server_time=now,
        notes=[NoteResponse.model_validate(n) for n in notes],
        tags=[TagResponse.model_validate(t) for t in tags],
        settings=settings_out,
    )


@router.post(
    "/push",
    response_model=SyncPushResponse,
    summary="Push changes",
    description="Upsert client changes (notes/tags/settings) into the server using last-write-wins.",
    operation_id="sync_push",
)
# PUBLIC_INTERFACE
def push_changes(
    payload: SyncPushRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncPushResponse:
    """Apply client changes to the server."""
    applied_note_ids: list[UUID] = []
    applied_tag_ids: list[UUID] = []

    # Upsert tags first (notes may reference tags)
    for t in payload.tags:
        existing = db.query(Tag).filter(Tag.user_id == current_user.id, Tag.id == t.id).one_or_none()
        if existing is None:
            tag = Tag(
                id=t.id,
                user_id=current_user.id,
                name=t.name.strip(),
                color=t.color,
                updated_at=t.updated_at,
            )
            db.add(tag)
            applied_tag_ids.append(t.id)
        else:
            if t.updated_at > existing.updated_at:
                existing.name = t.name.strip()
                existing.color = t.color
                existing.updated_at = t.updated_at
                db.add(existing)
                applied_tag_ids.append(t.id)

    # Cache tags by id for note association
    all_tags = db.query(Tag).filter(Tag.user_id == current_user.id).all()
    tags_by_id = {tag.id: tag for tag in all_tags}

    for n in payload.notes:
        existing = (
            db.query(Note)
            .options(selectinload(Note.tags))
            .filter(Note.user_id == current_user.id, Note.id == n.id)
            .one_or_none()
        )
        incoming_tags = [tags_by_id[tid] for tid in n.tag_ids if tid in tags_by_id]

        if existing is None:
            note = Note(
                id=n.id,
                user_id=current_user.id,
                title=n.title,
                content=n.content,
                is_pinned=n.is_pinned,
                is_favorite=n.is_favorite,
                version="1",
                created_at=_utcnow(),
                updated_at=n.updated_at,
                deleted_at=n.deleted_at,
                tags=incoming_tags,
            )
            db.add(note)
            applied_note_ids.append(n.id)
        else:
            if n.updated_at > existing.updated_at:
                existing.title = n.title
                existing.content = n.content
                existing.is_pinned = n.is_pinned
                existing.is_favorite = n.is_favorite
                existing.tags = incoming_tags
                existing.deleted_at = n.deleted_at
                existing.updated_at = n.updated_at
                # bump version token (simple integer string)
                try:
                    existing.version = str(int(existing.version) + 1)
                except Exception:
                    existing.version = existing.version or "1"
                db.add(existing)
                applied_note_ids.append(n.id)

    if payload.settings is not None:
        s = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).one_or_none()
        if s is None:
            s = UserSettings(user_id=current_user.id, theme=payload.settings.theme, updated_at=_utcnow())
        else:
            s.theme = payload.settings.theme
            s.updated_at = _utcnow()
        db.add(s)

    return SyncPushResponse(server_time=_utcnow(), applied_note_ids=applied_note_ids, applied_tag_ids=applied_tag_ids)
