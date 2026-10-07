"""Seeds a throwaway database for the load test (SCALE.md Stage 0 item 4).

    python -m scripts.load_seed OVERDUE_SCHEDULES LOGIN_ACCOUNTS

Creates OVERDUE_SCHEDULES survivors, each with one accepted trusted contact
and an active check-in schedule whose deadline (plus grace) has passed, so
the next alert pass must alert every one of them. Also creates
LOGIN_ACCOUNTS accounts named login-0001.. with the password LOAD_PASSWORD,
for the concurrent-login test. Writes straight to the database through the
app's models: the API would hash 1,000 passwords one at a time.

Refuses to run unless the database name ends in _test, like the test suite.
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_secret
from app.models.auth import User
from app.models.checkin import CheckinSchedule, TrustedContact

LOAD_PASSWORD = "load-test-password-only"


def main() -> int:
    overdue = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    logins = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    db_name = make_url(get_settings().database_url).database or ""
    if not db_name.endswith("_test"):
        print(f"refusing: database {db_name!r} is not a throwaway (_test) database", file=sys.stderr)
        return 2

    password_hash = hash_secret(LOAD_PASSWORD)  # one Argon2 hash, reused
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        users = []
        for i in range(overdue):
            user = User(id=uuid.uuid4(), username=f"load-{i:05d}", password_hash=password_hash)
            users.append(user)
            db.add(user)
            db.add(
                TrustedContact(
                    user_id=user.id,
                    nickname="Load contact",
                    contact_email=f"contact-{i:05d}@example.invalid",
                    status="accepted",
                    responded_at=now,
                )
            )
            db.add(
                CheckinSchedule(
                    user_id=user.id,
                    active=True,
                    interval_hours=24,
                    grace_hours=6,
                    last_checkin_at=now - timedelta(hours=48),
                    next_deadline_at=now - timedelta(hours=24),
                )
            )
        for i in range(logins):
            db.add(User(id=uuid.uuid4(), username=f"login-{i:04d}", password_hash=password_hash))
        db.commit()
    print(f"seeded {overdue} overdue schedules with one accepted contact each, {logins} login accounts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
