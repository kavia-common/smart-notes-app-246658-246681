"""
User settings routes (currently only theme).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.core.deps import get_current_user, get_db
from src.api.models import User, UserSettings
from src.api.schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get settings",
    description="Get settings for the authenticated user.",
    operation_id="settings_get",
)
# PUBLIC_INTERFACE
def get_settings_route(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SettingsResponse:
    """Get current user settings."""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).one_or_none()
    if settings is None:
        # Create defaults if missing
        settings = UserSettings(user_id=current_user.id, theme="light", updated_at=_utcnow())
        db.add(settings)
        db.flush()

    return SettingsResponse(theme=settings.theme, updated_at=settings.updated_at)


@router.put(
    "",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Update settings for the authenticated user.",
    operation_id="settings_update",
)
# PUBLIC_INTERFACE
def update_settings(
    payload: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Update user settings."""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).one_or_none()
    if settings is None:
        settings = UserSettings(user_id=current_user.id, theme="light", updated_at=_utcnow())

    settings.theme = payload.theme
    settings.updated_at = _utcnow()
    db.add(settings)
    db.flush()
    return SettingsResponse(theme=settings.theme, updated_at=settings.updated_at)
