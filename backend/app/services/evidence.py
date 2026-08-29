import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.auth import User
from ..models.evidence import CaseProfile, EvidenceEntry
from ..schemas.evidence import EncryptedBlob

logger = logging.getLogger("solusvires.evidence")


class EvidenceService:
    """Stores and returns opaque ciphertext only. Never inspects or logs entry content."""

    def get_salt(self, user: User) -> str | None:
        return user.evidence_salt

    def set_salt(self, db: Session, user: User, salt: str) -> None:
        if user.evidence_salt is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Evidence PIN salt is already set for this account.",
            )
        user.evidence_salt = salt
        db.commit()

    def get_case_profile(self, db: Session, user: User) -> CaseProfile | None:
        return db.query(CaseProfile).filter(CaseProfile.user_id == user.id).first()

    def upsert_case_profile(self, db: Session, user: User, blob: EncryptedBlob) -> CaseProfile:
        profile = self.get_case_profile(db, user)
        if profile is None:
            profile = CaseProfile(user_id=user.id, ciphertext=blob.ciphertext, iv=blob.iv)
            db.add(profile)
        else:
            profile.ciphertext = blob.ciphertext
            profile.iv = blob.iv
        db.commit()
        db.refresh(profile)
        logger.info("case_profile_saved")
        return profile

    def list_entries(self, db: Session, user: User) -> list[EvidenceEntry]:
        return (
            db.query(EvidenceEntry)
            .filter(EvidenceEntry.user_id == user.id)
            .order_by(EvidenceEntry.created_at.desc())
            .all()
        )

    def create_entry(self, db: Session, user: User, blob: EncryptedBlob) -> EvidenceEntry:
        entry = EvidenceEntry(user_id=user.id, ciphertext=blob.ciphertext, iv=blob.iv)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info("evidence_entry_created")
        return entry

    def _get_owned_entry(self, db: Session, user: User, entry_id: uuid.UUID) -> EvidenceEntry:
        entry = (
            db.query(EvidenceEntry)
            .filter(EvidenceEntry.id == entry_id, EvidenceEntry.user_id == user.id)
            .first()
        )
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found.")
        return entry

    def update_entry(
        self, db: Session, user: User, entry_id: uuid.UUID, blob: EncryptedBlob
    ) -> EvidenceEntry:
        entry = self._get_owned_entry(db, user, entry_id)
        entry.ciphertext = blob.ciphertext
        entry.iv = blob.iv
        db.commit()
        db.refresh(entry)
        logger.info("evidence_entry_updated")
        return entry

    def delete_entry(self, db: Session, user: User, entry_id: uuid.UUID) -> None:
        entry = self._get_owned_entry(db, user, entry_id)
        db.delete(entry)
        db.commit()
        logger.info("evidence_entry_deleted")
