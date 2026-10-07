from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.rate_limit import RateLimiter, client_ip
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.auth import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    LoginRequest,
    LoginResponse,
    LogoutOthersResponse,
    MeResponse,
    RecoverRequest,
    RecoverResponse,
    RegisterRequest,
    RegisterResponse,
    SessionInfo,
)
from ..services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
service = AuthService()

# Per-IP, on top of the per-(IP, username) slowdown in core/login_throttle.py -
# that alone doesn't stop one IP from spraying attempts across many usernames.
register_limiter = RateLimiter(max_requests=5, window_seconds=3600)
login_limiter = RateLimiter(max_requests=20, window_seconds=300)
recover_limiter = RateLimiter(max_requests=10, window_seconds=3600)


@router.post("/register", response_model=RegisterResponse, dependencies=[Depends(register_limiter)])
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    _, codes = service.register(db, payload)
    return RegisterResponse(ok=True, recovery_codes=codes)


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(login_limiter)])
async def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    service.login(db, response, payload, client_ip(request), request.headers.get("user-agent"))
    return LoginResponse(ok=True)


@router.post("/logout", response_model=LoginResponse)
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    sv_session: str | None = Cookie(default=None),
) -> LoginResponse:
    if sv_session:
        service.logout(db, response, sv_session)
    return LoginResponse(ok=True)


@router.post("/logout-all", response_model=LoginResponse)
async def logout_all(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LoginResponse:
    service.logout_all(db, response, user)
    return LoginResponse(ok=True)


@router.get("/sessions", response_model=list[SessionInfo])
async def sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    sv_session: str | None = Cookie(default=None),
) -> list[SessionInfo]:
    """Where you're signed in (P3-J1): device family and times, nothing that identifies a network."""
    return [SessionInfo(**row) for row in service.sessions(db, user, sv_session)]


@router.post("/logout-others", response_model=LogoutOthersResponse)
async def logout_others(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    sv_session: str | None = Cookie(default=None),
) -> LogoutOthersResponse:
    """Signs out every device except this one (P3-J1)."""
    return LogoutOthersResponse(ok=True, signed_out=service.logout_others(db, user, sv_session or ""))


@router.post("/recover", response_model=RecoverResponse, dependencies=[Depends(recover_limiter)])
async def recover(
    payload: RecoverRequest, response: Response, db: Session = Depends(get_db)
) -> RecoverResponse:
    service.recover(db, response, payload)
    return RecoverResponse(ok=True)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, evidence_pin_set=user.evidence_salt is not None)


@router.post("/delete-account", response_model=DeleteAccountResponse)
async def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteAccountResponse:
    service.delete_account(db, response, user, payload)
    return DeleteAccountResponse(ok=True)
