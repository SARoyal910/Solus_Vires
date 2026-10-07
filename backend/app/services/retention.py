"""Inactive-account retention (P3-H4). Off until counsel decides the period.

With INACTIVE_ACCOUNT_RETENTION_DAYS above zero, the maintenance pass deletes
accounts that have not signed in for that long AND have no active check-in
schedule. An active schedule means someone may be relying on alerts for a
person who has not opened the site; that account is never swept. Deleting
the user row cascades to everything (see AuthService.delete_account). There
is no warning email: survivor accounts have no email address by design.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.auth import User
from ..models.checkin import CheckinSchedule

logger = logging.getLogger("solusvires.retention")


def sweep_inactive_accounts(db: Session) -> int:
    days = get_settings().inactive_account_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    has_active_schedule = exists().where(
        CheckinSchedule.user_id == User.id, CheckinSchedule.active.is_(True)
    )
    stale = (
        db.query(User)
        .filter(
            # Never signed in: judge by creation. Otherwise by the last sign-in.
            ((User.last_login_at.is_(None)) & (User.created_at < cutoff))
            | ((User.last_login_at.isnot(None)) & (User.last_login_at < cutoff)),
            ~has_active_schedule,
        )
        .all()
    )
    for user in stale:
        db.delete(user)
    db.commit()
    if stale:
        logger.info("inactive_accounts_deleted", extra={"count": len(stale), "days": days})
    return len(stale)
