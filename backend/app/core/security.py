import hashlib
import hmac
import secrets
import uuid
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

# last_seen_at is only rewritten when it is at least this old, so ordinary
# browsing doesn't turn every authenticated read into a database write (M7).
LAST_SEEN_RESOLUTION = timedelta(minutes=5)

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


def normalize_recovery_code(code: str) -> str:
    """Codes are lowercase hex with a hyphen; tolerate case and stray spaces when typed back."""
    return "".join(code.split()).lower()


def recovery_code_digest(user_id: uuid.UUID, code: str) -> str:
    """Peppered HMAC-SHA256 of a recovery code, bound to its account.

    Recovery codes carry 80 random bits, so a fast keyed hash is enough and
    lets /recover find a code with one indexed lookup instead of up to ten
    Argon2 verifications (review M6). The pepper lives in the server's
    environment, not the database, so a database dump alone can't be used to
    test guesses.
    """
    key = get_settings().recovery_code_pepper.encode("utf-8")
    message = f"{user_id}:{normalize_recovery_code(code)}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


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


_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("CriOS/", "Chrome"),
    ("FxiOS/", "Firefox"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("CrOS", "Chromebook"),
    ("Linux", "Linux"),
)


def device_label(user_agent: str | None) -> str | None:
    """"Safari on iPhone" from a User-Agent: browser and OS family only (P3-J1).

    Deliberately lossy. The full string could fingerprint a device; the
    label only needs to let the survivor tell their phone from their laptop.
    """
    if not user_agent:
        return None
    browser = next((name for needle, name in _BROWSERS if needle in user_agent), "Browser")
    system = next((name for needle, name in _SYSTEMS if needle in user_agent), "a device")
    return f"{browser} on {system}"


def create_session(db: Session, response: Response, user: User, user_agent: str | None = None) -> None:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)

    db.add(
        SessionModel(
            id=_hash_token(raw_token),
            user_id=user.id,
            expires_at=expires_at,
            device_label=device_label(user_agent),
        )
    )
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        # Lax, not Strict: a survivor following a link from an email or text
        # must arrive logged in (review L1). Every state-changing route is a
        # JSON POST/PUT/DELETE with no CORS, so Lax still keeps them same-site.
        samesite="lax",
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


def delete_other_sessions(db: Session, user_id: uuid.UUID, keep_raw_token: str) -> int:
    """Signs out every other device; the one making the request stays (P3-J1)."""
    deleted = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == user_id, SessionModel.id != _hash_token(keep_raw_token))
        .delete()
    )
    db.commit()
    return deleted


def list_sessions(db: Session, user_id: uuid.UUID, current_raw_token: str | None) -> list[dict]:
    """The survivor's active sessions, without tokens, hashes or IPs (P3-J1)."""
    now = datetime.now(timezone.utc)
    current_hash = _hash_token(current_raw_token) if current_raw_token else None
    rows = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == user_id, SessionModel.expires_at > now)
        .order_by(SessionModel.last_seen_at.desc())
        .all()
    )
    return [
        {
            "current": row.id == current_hash,
            "device": row.device_label or "Unknown device",
            "created_at": row.created_at,
            "last_seen_at": row.last_seen_at,
        }
        for row in rows
    ]


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

    now = datetime.now(timezone.utc)
    if session_row.last_seen_at is None or now - session_row.last_seen_at >= LAST_SEEN_RESOLUTION:
        session_row.last_seen_at = now
        db.commit()

    user = db.get(User, session_row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user


def sweep_expired_sessions(db: Session) -> int:
    """Deletes session rows past their expiry. Run from the background loop (M7)."""
    deleted = db.query(SessionModel).filter(SessionModel.expires_at <= datetime.now(timezone.utc)).delete()
    db.commit()
    return deleted
