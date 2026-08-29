from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RecoverRequest,
    RecoverResponse,
    RegisterRequest,
    RegisterResponse,
)
from ..services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
service = AuthService()


@router.post("/register", response_model=RegisterResponse)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    _, codes = service.register(db, payload)
    return RegisterResponse(ok=True, recovery_codes=codes)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    service.login(db, response, payload)
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


@router.post("/recover", response_model=RecoverResponse)
async def recover(
    payload: RecoverRequest, response: Response, db: Session = Depends(get_db)
) -> RecoverResponse:
    service.recover(db, response, payload)
    return RecoverResponse(ok=True)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, evidence_pin_set=user.evidence_salt is not None)
