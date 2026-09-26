import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..models.auth import Session as SessionModel
from ..models.auth import User
from .config import get_settings
from .db import get_db

SESSION_COOKIE_NAME = "sv_session"

_hasher = PasswordHasher()


def hash_secret(value: str) -> str:
    """Hashes a password or recovery code. Never store or log the raw value."""
    return _hasher.hash(value)


def verify_secret(hashed: str, value: str) -> bool:
    try:
        return _hasher.verify(hashed, value)
    except VerifyMismatchError:
        return False


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [f"{secrets.token_hex(5)}-{secrets.token_hex(5)}" for _ in range(count)]


def register_failed_login(db: Session, user: User) -> None:
    """Counts failures on the account as a signal only. It never locks the
    account: see core/login_throttle.py for why, and for what slows guessing."""
    user.failed_login_count += 1
    db.commit()


def reset_failed_logins(db: Session, user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(db: Session, response: Response, user: User) -> None:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)

    db.add(
        SessionModel(
            id=_hash_token(raw_token),
            user_id=user.id,
            expires_at=expires_at,
        )
    )
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def delete_session(db: Session, raw_token: str) -> None:
    session_row = db.get(SessionModel, _hash_token(raw_token))
    if session_row is not None:
        db.delete(session_row)
        db.commit()


def delete_all_sessions(db: Session, user_id: str) -> None:
    db.query(SessionModel).filter(SessionModel.user_id == user_id).delete()
    db.commit()


def get_current_user(
    sv_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not sv_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    token_hash = _hash_token(sv_session)
    session_row = db.get(SessionModel, token_hash)
    if session_row is None or session_row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    session_row.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    user = db.get(User, session_row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user
