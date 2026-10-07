import base64
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.auth import User
from ..models.evidence import CaseProfile, EvidenceEntry
from ..models.vault import EvidenceAttachment, SafetyPlan
from ..schemas.evidence import EncryptedBlob
from ..schemas.vault import AttachmentCreate, RekeyAttachmentStage, RekeyRequest

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


    # ---------- PIN change (P3-J2) ----------

    def stage_rekeyed_attachment(
        self, db: Session, user: User, attachment_id: uuid.UUID, payload: RekeyAttachmentStage
    ) -> None:
        """Holds one photo's new ciphertext next to the old until the swap."""
        attachment = self.get_attachment(db, user, attachment_id)
        attachment.pending_ciphertext = base64.b64decode(payload.ciphertext, validate=True)
        attachment.pending_iv = payload.iv
        attachment.pending_rekey_id = payload.rekey_id
        db.commit()

    def rekey(self, db: Session, user: User, payload: RekeyRequest) -> tuple[int, int]:
        """Swaps the whole vault to the new key in one transaction, or changes nothing.

        Refuses (409) when the request does not cover exactly the notes,
        photos, profile and plan the account holds right now, or when any
        photo lacks a staged copy for this rekey id. Returns the counts.
        """
        if user.evidence_salt is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Set up a PIN first.")

        def mismatch(what: str) -> HTTPException:
            logger.info("vault_rekey_refused", extra={"reason": what})
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The vault changed while the PIN was being changed ({what}). Nothing was changed; try again.",
            )

        entries = {e.id: e for e in db.query(EvidenceEntry).filter(EvidenceEntry.user_id == user.id).all()}
        sent_entries = {e.id for e in payload.entries}
        if len(sent_entries) != len(payload.entries) or sent_entries != set(entries):
            raise mismatch("notes")

        attachments = {
            a.id: a for a in db.query(EvidenceAttachment).filter(EvidenceAttachment.user_id == user.id).all()
        }
        sent_attachments = {a.id for a in payload.attachments}
        if len(sent_attachments) != len(payload.attachments) or sent_attachments != set(attachments):
            raise mismatch("photos")
        for attachment in attachments.values():
            if attachment.pending_rekey_id != payload.rekey_id or attachment.pending_ciphertext is None:
                raise mismatch("a photo was not re-encrypted")

        profile = db.query(CaseProfile).filter(CaseProfile.user_id == user.id).first()
        if (profile is None) != (payload.profile is None):
            raise mismatch("profile")
        plan = db.query(SafetyPlan).filter(SafetyPlan.user_id == user.id).first()
        if (plan is None) != (payload.plan is None):
            raise mismatch("safety plan")

        # Everything matched: swap. One commit at the end, so a failure
        # anywhere rolls the whole vault back to the old key.
        for sent in payload.entries:
            entries[sent.id].ciphertext = sent.ciphertext
            entries[sent.id].iv = sent.iv
        for sent in payload.attachments:
            attachment = attachments[sent.id]
            attachment.ciphertext = attachment.pending_ciphertext
            attachment.iv = attachment.pending_iv
            attachment.size_bytes = len(attachment.pending_ciphertext)
            attachment.meta_ciphertext = sent.meta_ciphertext
            attachment.meta_iv = sent.meta_iv
            attachment.pending_ciphertext = None
            attachment.pending_iv = None
            attachment.pending_rekey_id = None
        if profile is not None and payload.profile is not None:
            profile.ciphertext = payload.profile.ciphertext
            profile.iv = payload.profile.iv
        if plan is not None and payload.plan is not None:
            plan.ciphertext = payload.plan.ciphertext
            plan.iv = payload.plan.iv
        user.evidence_salt = payload.salt
        user.evidence_key_check_ciphertext = payload.key_check.ciphertext
        user.evidence_key_check_iv = payload.key_check.iv
        db.commit()
        logger.info("vault_rekeyed")
        return len(entries), len(attachments)

    def discard_stale_rekey_copies(self, db: Session) -> int:
        """Maintenance: drops staged copies left by abandoned PIN changes."""
        count = (
            db.query(EvidenceAttachment)
            .filter(EvidenceAttachment.pending_rekey_id.isnot(None))
            .update(
                {
                    EvidenceAttachment.pending_ciphertext: None,
                    EvidenceAttachment.pending_iv: None,
                    EvidenceAttachment.pending_rekey_id: None,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return count
