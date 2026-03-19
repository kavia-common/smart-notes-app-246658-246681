"""
Tag management routes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.core.deps import get_current_user, get_db
from src.api.models import Tag, User
from src.api.schemas import TagCreateRequest, TagResponse, TagUpdateRequest

router = APIRouter(prefix="/tags", tags=["tags"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "",
    response_model=list[TagResponse],
    summary="List tags",
    description="List tags belonging to the authenticated user.",
    operation_id="tags_list",
)
# PUBLIC_INTERFACE
def list_tags(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TagResponse]:
    """List user tags."""
    tags = (
        db.query(Tag)
        .filter(Tag.user_id == current_user.id)
        .order_by(Tag.name.asc())
        .all()
    )
    return [TagResponse.model_validate(t) for t in tags]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag for the authenticated user.",
    operation_id="tags_create",
)
# PUBLIC_INTERFACE
def create_tag(
    payload: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagResponse:
    """Create a tag."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name cannot be empty")

    existing = db.query(Tag).filter(Tag.user_id == current_user.id, Tag.name == name).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag name already exists")

    tag = Tag(user_id=current_user.id, name=name, color=payload.color, updated_at=_utcnow())
    db.add(tag)
    db.flush()
    return TagResponse.model_validate(tag)


@router.put(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Update tag",
    description="Update an existing tag.",
    operation_id="tags_update",
)
# PUBLIC_INTERFACE
def update_tag(
    tag_id: UUID,
    payload: TagUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagResponse:
    """Update a tag."""
    tag = db.query(Tag).filter(Tag.user_id == current_user.id, Tag.id == tag_id).one_or_none()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name cannot be empty")
        # uniqueness check
        conflict = (
            db.query(Tag)
            .filter(Tag.user_id == current_user.id, Tag.name == name, Tag.id != tag_id)
            .one_or_none()
        )
        if conflict is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag name already exists")
        tag.name = name

    if payload.color is not None:
        tag.color = payload.color

    tag.updated_at = _utcnow()
    db.add(tag)
    db.flush()
    return TagResponse.model_validate(tag)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Notes will simply lose this tag association.",
    operation_id="tags_delete",
)
# PUBLIC_INTERFACE
def delete_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a tag."""
    tag = db.query(Tag).filter(Tag.user_id == current_user.id, Tag.id == tag_id).one_or_none()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    db.delete(tag)
