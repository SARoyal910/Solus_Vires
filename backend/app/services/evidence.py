import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.auth import User
from ..models.evidence import CaseProfile, EvidenceEntry
from ..schemas.evidence import EncryptedBlob, KeyCheck
from . import attest

logger = logging.getLogger("solusvires.evidence")


class EvidenceService:
    """Stores and returns opaque ciphertext only. Never inspects or logs entry content."""

    def get_salt(self, user: User) -> str | None:
        return user.evidence_salt

    def get_key_check(self, user: User) -> KeyCheck | None:
        if user.evidence_key_check_ciphertext is None or user.evidence_key_check_iv is None:
            return None
        return KeyCheck(ciphertext=user.evidence_key_check_ciphertext, iv=user.evidence_key_check_iv)

    def set_salt(self, db: Session, user: User, salt: str, key_check: KeyCheck | None) -> None:
        if user.evidence_salt is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Evidence PIN salt is already set for this account.",
            )
        user.evidence_salt = salt
        if key_check is not None:
            user.evidence_key_check_ciphertext = key_check.ciphertext
            user.evidence_key_check_iv = key_check.iv
        db.commit()

    def set_key_check(self, db: Session, user: User, key_check: KeyCheck) -> None:
        """One-time backfill for accounts whose PIN predates the key-check.

        Write-once, like the salt: once a key-check exists it is the only thing
        that decides whether a PIN is right, so it must not be replaceable.
        """
        if user.evidence_salt is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Set up a PIN first.")
        if user.evidence_key_check_ciphertext is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account's PIN check is already set.",
            )
        user.evidence_key_check_ciphertext = key_check.ciphertext
        user.evidence_key_check_iv = key_check.iv
        db.commit()

    def get_case_profile(self, db: Session, user: User) -> CaseProfile | None:
        return db.query(CaseProfile).filter(CaseProfile.user_id == user.id).first()

    def upsert_case_profile(self, db: Session, user: User, blob: EncryptedBlob) -> CaseProfile:
        profile = self.get_case_profile(db, user)
        if profile is None:
            profile = CaseProfile(user_id=user.id, ciphertext=blob.ciphertext, iv=blob.iv)
            db.add(profile)
            db.flush()
            attest.record(db, user.id, "profile", profile.id, blob.ciphertext, "saved")
        else:
            profile.ciphertext = blob.ciphertext
            profile.iv = blob.iv
            attest.record(db, user.id, "profile", profile.id, blob.ciphertext, "edited")
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
        db.flush()
        attest.record(db, user.id, "entry", entry.id, blob.ciphertext, "saved")
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
        attest.record(db, user.id, "entry", entry.id, blob.ciphertext, "edited")
        db.commit()
        db.refresh(entry)
        logger.info("evidence_entry_updated")
        return entry

    def delete_entry(self, db: Session, user: User, entry_id: uuid.UUID) -> None:
        entry = self._get_owned_entry(db, user, entry_id)
        db.delete(entry)
        db.commit()
        logger.info("evidence_entry_deleted")
