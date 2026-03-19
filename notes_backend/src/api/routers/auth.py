"""
Authentication routes: register, login, and current-user profile.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.core.deps import get_current_user, get_db
from src.api.core.security import create_access_token, hash_password, verify_password
from src.api.models import User
from src.api.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account and returns a JWT access token.",
    operation_id="auth_register",
)
# PUBLIC_INTERFACE
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new user."""
    existing = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()  # ensures user.id is available

    token = create_access_token(user_id=str(user.id), email=user.email)
    return TokenResponse(**token, user=UserPublic.model_validate(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticates a user and returns a JWT access token.",
    operation_id="auth_login",
)
# PUBLIC_INTERFACE
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Login with email/password."""
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user_id=str(user.id), email=user.email)
    return TokenResponse(**token, user=UserPublic.model_validate(user))


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user",
    description="Returns the authenticated user's profile.",
    operation_id="auth_me",
)
# PUBLIC_INTERFACE
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Get the current authenticated user profile."""
    return UserPublic.model_validate(current_user)
