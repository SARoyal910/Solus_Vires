import base64
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.auth import User
from ..models.evidence import EvidenceEntry
from ..models.vault import EvidenceAttachment, SafetyPlan
from ..schemas.evidence import EncryptedBlob
from ..schemas.vault import AttachmentCreate

logger = logging.getLogger("solusvires.vault")

# Keeps one account from filling the database. 200 photos at the 5 MB cap is
# about 1 GB; typical screenshots are far smaller.
MAX_ATTACHMENTS_PER_USER = 200


class VaultService:
    """Stores and returns opaque ciphertext only, scoped to its owner.

    Like EvidenceService: never inspects or logs content, and answers 404 (not
    403) for anything that belongs to someone else, so ids reveal nothing.
    """

    def get_safety_plan(self, db: Session, user: User) -> SafetyPlan | None:
        return db.query(SafetyPlan).filter(SafetyPlan.user_id == user.id).first()

    def upsert_safety_plan(self, db: Session, user: User, blob: EncryptedBlob) -> SafetyPlan:
        plan = self.get_safety_plan(db, user)
        if plan is None:
            plan = SafetyPlan(user_id=user.id, ciphertext=blob.ciphertext, iv=blob.iv)
            db.add(plan)
        else:
            plan.ciphertext = blob.ciphertext
            plan.iv = blob.iv
        db.commit()
        db.refresh(plan)
        logger.info("safety_plan_saved")
        return plan

    def delete_safety_plan(self, db: Session, user: User) -> None:
        plan = self.get_safety_plan(db, user)
        if plan is not None:
            db.delete(plan)
            db.commit()
            logger.info("safety_plan_deleted")

    def create_attachment(self, db: Session, user: User, payload: AttachmentCreate) -> EvidenceAttachment:
        entry = (
            db.query(EvidenceEntry)
            .filter(EvidenceEntry.id == payload.entry_id, EvidenceEntry.user_id == user.id)
            .first()
        )
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found.")
        count = db.scalar(
            select(func.count()).select_from(EvidenceAttachment).where(EvidenceAttachment.user_id == user.id)
        )
        if count >= MAX_ATTACHMENTS_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You can keep up to {MAX_ATTACHMENTS_PER_USER} photos. Delete some to add more.",
            )
        raw = base64.b64decode(payload.ciphertext)
        attachment = EvidenceAttachment(
            user_id=user.id,
            entry_id=entry.id,
            ciphertext=raw,
            iv=payload.iv,
            meta_ciphertext=payload.meta_ciphertext,
            meta_iv=payload.meta_iv,
            size_bytes=len(raw),
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        logger.info("evidence_attachment_created")
        return attachment

    def list_attachments(self, db: Session, user: User, entry_id: uuid.UUID | None = None) -> list[EvidenceAttachment]:
        query = db.query(EvidenceAttachment).filter(EvidenceAttachment.user_id == user.id)
        if entry_id is not None:
            query = query.filter(EvidenceAttachment.entry_id == entry_id)
        return query.order_by(EvidenceAttachment.created_at.asc()).all()

    def get_attachment(self, db: Session, user: User, attachment_id: uuid.UUID) -> EvidenceAttachment:
        attachment = (
            db.query(EvidenceAttachment)
            .filter(EvidenceAttachment.id == attachment_id, EvidenceAttachment.user_id == user.id)
            .first()
        )
        if attachment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
        return attachment

    def delete_attachment(self, db: Session, user: User, attachment_id: uuid.UUID) -> None:
        attachment = self.get_attachment(db, user, attachment_id)
        db.delete(attachment)
        db.commit()
        logger.info("evidence_attachment_deleted")
