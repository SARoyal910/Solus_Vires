"""Records attestation rows on every save (P3-H1). No-op when the key is unset."""

import logging
import uuid

from sqlalchemy.orm import Session

from ..core import attestation
from ..models.evidence import EvidenceAttestation

logger = logging.getLogger("solusvires.attestation")


def record(
    db: Session, user_id: uuid.UUID, kind: str, item_id: uuid.UUID, ciphertext: str | bytes, reason: str
) -> None:
    """Adds the signed row to the session; the caller commits with the item.

    `reason` is "saved" for a first save, "edited" for a change the survivor
    made, "rekeyed" for a PIN change. Supersedes the latest row for the item.
    """
    if not attestation.enabled():
        return
    previous = (
        db.query(EvidenceAttestation)
        .filter(EvidenceAttestation.item_id == item_id, EvidenceAttestation.kind == kind)
        .order_by(EvidenceAttestation.attested_at.desc())
        .first()
    )
    digest = attestation.ciphertext_sha256(ciphertext)
    at = attestation.now()
    db.add(
        EvidenceAttestation(
            user_id=user_id,
            kind=kind,
            item_id=item_id,
            ciphertext_sha256=digest,
            attested_at=at,
            key_id=attestation.key_id(),
            signature=attestation.sign(kind, str(item_id), digest, at),
            reason=reason if previous is not None else "saved",
            supersedes=previous.id if previous is not None else None,
        )
    )


def list_for(db: Session, user_id: uuid.UUID) -> list[EvidenceAttestation]:
    return (
        db.query(EvidenceAttestation)
        .filter(EvidenceAttestation.user_id == user_id)
        .order_by(EvidenceAttestation.attested_at.asc())
        .all()
    )
