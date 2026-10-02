"""Safety plan and photo attachments for the encrypted notes vault (P2-E7, P2-E8).

Same prefix as the notes API, so the no-store rule in core/middleware.py and
the nginx body-size exception for attachments cover these routes too.
"""

import base64
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.security import get_current_user
from ..models.auth import User
from ..models.vault import EvidenceAttachment
from ..schemas.evidence import EncryptedBlob
from ..schemas.vault import AttachmentCreate, AttachmentData, AttachmentInfo, SafetyPlanResponse
from ..services.vault import VaultService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
service = VaultService()


def _info(a: EvidenceAttachment) -> AttachmentInfo:
    return AttachmentInfo(
        id=a.id,
        entry_id=a.entry_id,
        iv=a.iv,
        meta_ciphertext=a.meta_ciphertext,
        meta_iv=a.meta_iv,
        size_bytes=a.size_bytes,
        created_at=a.created_at,
    )


@router.get("/safety-plan", response_model=SafetyPlanResponse | None)
async def get_safety_plan(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SafetyPlanResponse | None:
    plan = service.get_safety_plan(db, user)
    if plan is None:
        return None
    return SafetyPlanResponse(ciphertext=plan.ciphertext, iv=plan.iv, updated_at=plan.updated_at)


@router.put("/safety-plan", response_model=SafetyPlanResponse)
async def put_safety_plan(
    payload: EncryptedBlob,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SafetyPlanResponse:
    plan = service.upsert_safety_plan(db, user, payload)
    return SafetyPlanResponse(ciphertext=plan.ciphertext, iv=plan.iv, updated_at=plan.updated_at)


@router.delete("/safety-plan")
async def delete_safety_plan(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, bool]:
    service.delete_safety_plan(db, user)
    return {"ok": True}


@router.get("/attachments", response_model=list[AttachmentInfo])
async def list_attachments(
    entry_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttachmentInfo]:
    return [_info(a) for a in service.list_attachments(db, user, entry_id)]


@router.post("/attachments", response_model=AttachmentInfo)
async def create_attachment(
    payload: AttachmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttachmentInfo:
    return _info(service.create_attachment(db, user, payload))


@router.get("/attachments/{attachment_id}", response_model=AttachmentData)
async def get_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttachmentData:
    a = service.get_attachment(db, user, attachment_id)
    return AttachmentData(id=a.id, ciphertext=base64.b64encode(a.ciphertext).decode("ascii"), iv=a.iv)


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    service.delete_attachment(db, user, attachment_id)
    return {"ok": True}
