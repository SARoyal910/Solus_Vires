import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.login_throttle import login_throttle
from ..core.security import (
    create_session,
    delete_all_sessions,
    delete_session,
    generate_recovery_codes,
    hash_secret,
    register_failed_login,
    reset_failed_logins,
    verify_secret,
)
from ..models.auth import RecoveryCode, User
from ..schemas.auth import DeleteAccountRequest, LoginRequest, RecoverRequest, RegisterRequest

logger = logging.getLogger("solusvires.auth")


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.strip().encode("utf-8")).digest()


def check_signup_allowed(invite_code: str | None) -> None:
    """New accounts need an invite code until sign-ups are opened (review H6)."""
    settings = get_settings()
    if settings.beta_signups_open:
        return
    if not settings.beta_invite_codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="New accounts are paused while the site is being reviewed. Everything else on the site is open.",
        )
    supplied = _digest(invite_code or "")
    # Compare every code, in constant time, so timing doesn't hint at a near miss.
    matched = False
    for code in settings.beta_invite_codes:
        matched |= hmac.compare_digest(supplied, _digest(code))
    if not matched:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That invite code isn't valid.")


class AuthService:
    """Handles account lifecycle. Never logs a password, recovery code, or session token."""

    def register(self, db: Session, payload: RegisterRequest) -> tuple[User, list[str]]:
        check_signup_allowed(payload.invite_code)
        existing = db.query(User).filter(User.username == payload.username).first()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is taken.")

        user = User(username=payload.username, password_hash=hash_secret(payload.password))
        db.add(user)
        db.flush()

        codes = generate_recovery_codes()
        for code in codes:
            db.add(RecoveryCode(user_id=user.id, code_hash=hash_secret(code)))
        db.commit()

        logger.info("account_registered")
        return user, codes

    def login(self, db: Session, response: Response, payload: LoginRequest, client_ip: str) -> User:
        login_throttle.check(client_ip, payload.username)

        user = db.query(User).filter(User.username == payload.username).first()
        if user is None:
            login_throttle.record_failure(client_ip, payload.username)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

        if not verify_secret(user.password_hash, payload.password):
            login_throttle.record_failure(client_ip, payload.username)
            register_failed_login(db, user)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

        login_throttle.record_success(client_ip, payload.username)
        reset_failed_logins(db, user)
        create_session(db, response, user)
        logger.info("account_login")
        return user

    def logout(self, db: Session, response: Response, raw_token: str) -> None:
        delete_session(db, raw_token)
        response.delete_cookie("sv_session", path="/")

    def logout_all(self, db: Session, response: Response, user: User) -> None:
        delete_all_sessions(db, str(user.id))
        response.delete_cookie("sv_session", path="/")
        logger.info("account_logout_all")

    def recover(self, db: Session, response: Response, payload: RecoverRequest) -> None:
        user = db.query(User).filter(User.username == payload.username).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recovery code.")

        matching_code = None
        for code in db.query(RecoveryCode).filter(
            RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
        ):
            if verify_secret(code.code_hash, payload.recovery_code):
                matching_code = code
                break

        if matching_code is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recovery code.")

        matching_code.used_at = datetime.now(timezone.utc)
        user.password_hash = hash_secret(payload.new_password)
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()
        login_throttle.forget_username(user.username)

        delete_all_sessions(db, str(user.id))
        response.delete_cookie("sv_session", path="/")
        logger.info("account_recovered")

    def delete_account(
        self, db: Session, response: Response, user: User, payload: DeleteAccountRequest
    ) -> None:
        """Permanently deletes the account and everything tied to it.

        Foreign keys on every child table (sessions, recovery codes,
        evidence/case profile, trusted contacts and their push
        subscriptions, the check-in schedule) are ``ondelete="CASCADE"``, so
        deleting the user row is genuinely sufficient - there is nothing left
        behind for this account anywhere in the database.
        """
        if not verify_secret(user.password_hash, payload.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")

        db.delete(user)
        db.commit()
        response.delete_cookie("sv_session", path="/")
        logger.info("account_deleted")
