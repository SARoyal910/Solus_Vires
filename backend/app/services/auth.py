import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.security import (
    create_session,
    delete_all_sessions,
    delete_session,
    generate_recovery_codes,
    hash_secret,
    is_locked_out,
    register_failed_login,
    reset_failed_logins,
    verify_secret,
)
from ..models.auth import RecoveryCode, User
from ..schemas.auth import LoginRequest, RecoverRequest, RegisterRequest

logger = logging.getLogger("solusvires.auth")


class AuthService:
    """Handles account lifecycle. Never logs a password, recovery code, or session token."""

    def register(self, db: Session, payload: RegisterRequest) -> tuple[User, list[str]]:
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

    def login(self, db: Session, response: Response, payload: LoginRequest) -> User:
        user = db.query(User).filter(User.username == payload.username).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

        if is_locked_out(user):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later.",
            )

        if not verify_secret(user.password_hash, payload.password):
            register_failed_login(db, user)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

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

        delete_all_sessions(db, str(user.id))
        response.delete_cookie("sv_session", path="/")
        logger.info("account_recovered")
