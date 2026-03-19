"""
Note management routes: CRUD + search/filter.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from src.api.core.deps import get_current_user, get_db
from src.api.models import Note, Tag, User
from src.api.schemas import NoteCreateRequest, NoteResponse, NoteUpdateRequest

router = APIRouter(prefix="/notes", tags=["notes"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bump_version(current: str) -> str:
    """Increment an opaque version token stored as a string integer."""
    try:
        return str(int(current) + 1)
    except Exception:
        return str(uuid.uuid4())


def _get_note_or_404(db: Session, *, user_id: UUID, note_id: UUID) -> Note:
    note = (
        db.query(Note)
        .options(selectinload(Note.tags))
        .filter(Note.user_id == user_id, Note.id == note_id)
        .one_or_none()
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get(
    "",
    response_model=list[NoteResponse],
    summary="List notes",
    description="List notes for the authenticated user. Supports search and tag filtering.",
    operation_id="notes_list",
)
# PUBLIC_INTERFACE
def list_notes(
    q: Optional[str] = Query(None, description="Search query (matches title/content)."),
    tag_id: Optional[UUID] = Query(None, description="Filter by tag id."),
    pinned: Optional[bool] = Query(None, description="Filter by pinned status."),
    favorite: Optional[bool] = Query(None, description="Filter by favorite status."),
    include_deleted: bool = Query(False, description="Include soft-deleted notes."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NoteResponse]:
    """List/search notes."""
    query = (
        db.query(Note)
        .options(selectinload(Note.tags))
        .filter(Note.user_id == current_user.id)
    )

    if not include_deleted:
        query = query.filter(Note.deleted_at.is_(None))

    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Note.title.ilike(like)) | (Note.content.ilike(like)))

    if pinned is not None:
        query = query.filter(Note.is_pinned == pinned)

    if favorite is not None:
        query = query.filter(Note.is_favorite == favorite)

    if tag_id is not None:
        query = query.join(Note.tags).filter(Tag.id == tag_id)

    notes = query.order_by(Note.updated_at.desc()).all()
    return [NoteResponse.model_validate(n) for n in notes]


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
    description="Create a new note. Clients may provide an ID for offline-first workflows.",
    operation_id="notes_create",
)
# PUBLIC_INTERFACE
def create_note(
    payload: NoteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Create a note."""
    note_id = payload.id or uuid.uuid4()
    existing = db.query(Note).filter(Note.user_id == current_user.id, Note.id == note_id).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Note with this ID already exists")

    tags = []
    if payload.tag_ids:
        tags = (
            db.query(Tag)
            .filter(Tag.user_id == current_user.id, Tag.id.in_(payload.tag_ids))
            .all()
        )

    now = _utcnow()
    note = Note(
        id=note_id,
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        is_pinned=payload.is_pinned,
        is_favorite=payload.is_favorite,
        version="1",
        created_at=now,
        updated_at=now,
        deleted_at=None,
        tags=tags,
    )
    db.add(note)
    db.flush()
    db.refresh(note)
    return NoteResponse.model_validate(note)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get note",
    description="Fetch a single note by id.",
    operation_id="notes_get",
)
# PUBLIC_INTERFACE
def get_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Get note by ID."""
    note = _get_note_or_404(db, user_id=current_user.id, note_id=note_id)
    return NoteResponse.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update note",
    description="Update a note (partial update). Can also soft-delete/restore.",
    operation_id="notes_update",
)
# PUBLIC_INTERFACE
def update_note(
    note_id: UUID,
    payload: NoteUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Update note by ID."""
    note = _get_note_or_404(db, user_id=current_user.id, note_id=note_id)

    changed = False

    if payload.title is not None:
        note.title = payload.title
        changed = True
    if payload.content is not None:
        note.content = payload.content
        changed = True
    if payload.is_pinned is not None:
        note.is_pinned = payload.is_pinned
        changed = True
    if payload.is_favorite is not None:
        note.is_favorite = payload.is_favorite
        changed = True

    if payload.tag_ids is not None:
        tags = []
        if payload.tag_ids:
            tags = (
                db.query(Tag)
                .filter(Tag.user_id == current_user.id, Tag.id.in_(payload.tag_ids))
                .all()
            )
        note.tags = tags
        changed = True

    if payload.deleted is not None:
        if payload.deleted:
            note.deleted_at = payload.updated_at or _utcnow()
        else:
            note.deleted_at = None
        changed = True

    if changed:
        note.updated_at = payload.updated_at or _utcnow()
        note.version = _bump_version(note.version)

    db.add(note)
    db.flush()
    db.refresh(note)
    return NoteResponse.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Soft-delete a note (sets deleted_at).",
    operation_id="notes_delete",
)
# PUBLIC_INTERFACE
def delete_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete a note."""
    note = _get_note_or_404(db, user_id=current_user.id, note_id=note_id)
    if note.deleted_at is None:
        note.deleted_at = _utcnow()
        note.updated_at = _utcnow()
        note.version = _bump_version(note.version)
        db.add(note)
