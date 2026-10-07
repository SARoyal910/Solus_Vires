import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core import attestation
from ..core.db import get_db
from ..core.security import get_current_user
from ..models.auth import User
from ..schemas.evidence import (
    AttestationKeyResponse,
    AttestationResponse,
    CaseProfileResponse,
    EncryptedBlob,
    EvidenceEntryResponse,
    KeyCheck,
    SaltResponse,
    SetSaltRequest,
)
from ..services import attest
from ..services.evidence import EvidenceService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
service = EvidenceService()


@router.get("/salt", response_model=SaltResponse)
async def get_salt(user: User = Depends(get_current_user)) -> SaltResponse:
    return SaltResponse(salt=service.get_salt(user), key_check=service.get_key_check(user))


@router.put("/salt", response_model=SaltResponse)
async def set_salt(
    payload: SetSaltRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SaltResponse:
    service.set_salt(db, user, payload.salt, payload.key_check)
    return SaltResponse(salt=user.evidence_salt, key_check=service.get_key_check(user))


@router.put("/key-check", response_model=SaltResponse)
async def set_key_check(
    payload: KeyCheck,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SaltResponse:
    service.set_key_check(db, user, payload)
    return SaltResponse(salt=user.evidence_salt, key_check=service.get_key_check(user))


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


# ---------- Attestation (P3-H1) ----------


@router.get("/attestations", response_model=list[AttestationResponse])
async def list_attestations(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AttestationResponse]:
    """Every signed statement about this account's ciphertext, oldest first. Hashes, never content."""
    return [AttestationResponse.model_validate(a, from_attributes=True) for a in attest.list_for(db, user.id)]


@router.get("/attestation-key", response_model=AttestationKeyResponse)
async def attestation_key() -> AttestationKeyResponse:
    """The public key an export is verified against. Public, and also printed on /trust.html."""
    if not attestation.enabled():
        return AttestationKeyResponse(enabled=False)
    return AttestationKeyResponse(enabled=True, key_id=attestation.key_id(), public_key=attestation.public_key_b64())
