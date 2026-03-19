"""
Pydantic models (schemas) for API requests/responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Human-readable error message.")


class UserPublic(BaseModel):
    """Public user profile information."""

    id: UUID = Field(..., description="User ID.")
    email: EmailStr = Field(..., description="User email address.")

    class Config:
        from_attributes = True


class AuthRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (must be unique).")
    password: str = Field(..., min_length=6, description="User password (min length 6).")


class AuthLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email.")
    password: str = Field(..., description="User password.")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT bearer access token.")
    token_type: str = Field("bearer", description="Token type (always 'bearer').")
    expires_at: int = Field(..., description="Unix timestamp (seconds) when the token expires.")
    user: UserPublic = Field(..., description="Authenticated user.")


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="Tag name.")
    color: Optional[str] = Field(None, description="Optional color value (e.g., hex).")


class TagCreateRequest(TagBase):
    pass


class TagUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80, description="New tag name.")
    color: Optional[str] = Field(None, description="New color value (e.g., hex).")


class TagResponse(TagBase):
    id: UUID = Field(..., description="Tag ID.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")

    class Config:
        from_attributes = True


class NoteBase(BaseModel):
    title: str = Field("", max_length=300, description="Note title.")
    content: str = Field("", description="Note content/body.")
    is_pinned: bool = Field(False, description="Whether the note is pinned.")
    is_favorite: bool = Field(False, description="Whether the note is favorited.")
    tag_ids: List[UUID] = Field(default_factory=list, description="Tags to apply to the note.")


class NoteCreateRequest(NoteBase):
    id: Optional[UUID] = Field(
        None,
        description="Optional client-generated note ID (useful for offline-first sync).",
    )


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=300, description="Updated title.")
    content: Optional[str] = Field(None, description="Updated content.")
    is_pinned: Optional[bool] = Field(None, description="Updated pinned flag.")
    is_favorite: Optional[bool] = Field(None, description="Updated favorite flag.")
    tag_ids: Optional[List[UUID]] = Field(None, description="Replace tag IDs for this note.")
    deleted: Optional[bool] = Field(None, description="Soft-delete (true) or restore (false) the note.")
    updated_at: Optional[datetime] = Field(
        None,
        description="Client-side updated timestamp for sync conflict resolution.",
    )


class NoteResponse(BaseModel):
    id: UUID = Field(..., description="Note ID.")
    title: str = Field(..., description="Note title.")
    content: str = Field(..., description="Note content/body.")
    is_pinned: bool = Field(..., description="Whether the note is pinned.")
    is_favorite: bool = Field(..., description="Whether the note is favorited.")
    version: str = Field(..., description="Opaque version token (increments on changes).")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
    deleted_at: Optional[datetime] = Field(None, description="Soft-delete timestamp.")
    tags: List[TagResponse] = Field(default_factory=list, description="Tags on this note.")

    class Config:
        from_attributes = True


class SettingsResponse(BaseModel):
    theme: str = Field(..., description="Theme preference: 'light' or 'dark'.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class SettingsUpdateRequest(BaseModel):
    theme: str = Field(..., description="Theme preference: 'light' or 'dark'.")


class SyncPullResponse(BaseModel):
    server_time: datetime = Field(..., description="Server time for client clock alignment.")
    notes: List[NoteResponse] = Field(default_factory=list, description="Notes changed since the given timestamp.")
    tags: List[TagResponse] = Field(default_factory=list, description="Tags changed since the given timestamp.")
    settings: Optional[SettingsResponse] = Field(None, description="Settings if changed since the given timestamp.")


class SyncPushNote(BaseModel):
    id: UUID = Field(..., description="Note ID.")
    title: str = Field("", max_length=300, description="Note title.")
    content: str = Field("", description="Note content.")
    is_pinned: bool = Field(False, description="Pinned flag.")
    is_favorite: bool = Field(False, description="Favorite flag.")
    tag_ids: List[UUID] = Field(default_factory=list, description="Tags for the note.")
    updated_at: datetime = Field(..., description="Client updated_at timestamp.")
    deleted_at: Optional[datetime] = Field(None, description="Soft-delete timestamp if deleted.")


class SyncPushTag(BaseModel):
    id: UUID = Field(..., description="Tag ID.")
    name: str = Field(..., min_length=1, max_length=80, description="Tag name.")
    color: Optional[str] = Field(None, description="Tag color.")
    updated_at: datetime = Field(..., description="Client updated_at timestamp.")


class SyncPushRequest(BaseModel):
    notes: List[SyncPushNote] = Field(default_factory=list, description="Notes to upsert to the server.")
    tags: List[SyncPushTag] = Field(default_factory=list, description="Tags to upsert to the server.")
    settings: Optional[SettingsUpdateRequest] = Field(None, description="Settings to update.")


class SyncPushResponse(BaseModel):
    server_time: datetime = Field(..., description="Server time after applying changes.")
    applied_note_ids: List[UUID] = Field(default_factory=list, description="Notes accepted/applied by server.")
    applied_tag_ids: List[UUID] = Field(default_factory=list, description="Tags accepted/applied by server.")
