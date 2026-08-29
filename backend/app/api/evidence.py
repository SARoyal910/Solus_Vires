import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.evidence import (
    CaseProfileResponse,
    EncryptedBlob,
    EvidenceEntryResponse,
    SaltResponse,
    SetSaltRequest,
)
from ..services.evidence import EvidenceService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
service = EvidenceService()


@router.get("/salt", response_model=SaltResponse)
async def get_salt(user: User = Depends(get_current_user)) -> SaltResponse:
    return SaltResponse(salt=service.get_salt(user))


@router.put("/salt", response_model=SaltResponse)
async def set_salt(
    payload: SetSaltRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SaltResponse:
    service.set_salt(db, user, payload.salt)
    return SaltResponse(salt=payload.salt)


@router.get("/case-profile", response_model=CaseProfileResponse | None)
async def get_case_profile(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CaseProfileResponse | None:
    profile = service.get_case_profile(db, user)
    if profile is None:
        return None
    return CaseProfileResponse(ciphertext=profile.ciphertext, iv=profile.iv, updated_at=profile.updated_at)


@router.put("/case-profile", response_model=CaseProfileResponse)
async def put_case_profile(
    payload: EncryptedBlob,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseProfileResponse:
    profile = service.upsert_case_profile(db, user, payload)
    return CaseProfileResponse(ciphertext=profile.ciphertext, iv=profile.iv, updated_at=profile.updated_at)


@router.get("/entries", response_model=list[EvidenceEntryResponse])
async def list_entries(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[EvidenceEntryResponse]:
    entries = service.list_entries(db, user)
    return [
        EvidenceEntryResponse(
            id=e.id, ciphertext=e.ciphertext, iv=e.iv, created_at=e.created_at, updated_at=e.updated_at
        )
        for e in entries
    ]


@router.post("/entries", response_model=EvidenceEntryResponse)
async def create_entry(
    payload: EncryptedBlob,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceEntryResponse:
    entry = service.create_entry(db, user, payload)
    return EvidenceEntryResponse(
        id=entry.id, ciphertext=entry.ciphertext, iv=entry.iv, created_at=entry.created_at, updated_at=entry.updated_at
    )


@router.put("/entries/{entry_id}", response_model=EvidenceEntryResponse)
async def update_entry(
    entry_id: uuid.UUID,
    payload: EncryptedBlob,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceEntryResponse:
    entry = service.update_entry(db, user, entry_id, payload)
    return EvidenceEntryResponse(
        id=entry.id, ciphertext=entry.ciphertext, iv=entry.iv, created_at=entry.created_at, updated_at=entry.updated_at
    )


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    service.delete_entry(db, user, entry_id)
    return {"ok": True}
