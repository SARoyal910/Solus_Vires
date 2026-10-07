"""Times one alert pass over the seeded database (SCALE.md Stage 0 item 4).

    LOAD_EMAIL_LATENCY_MS=0 python -m scripts.load_alert_pass

Email and push are replaced with counters, so nothing leaves the machine.
LOAD_EMAIL_LATENCY_MS (default 0) adds a sleep per email to model a real
provider round trip; the pass sends serially, so this is what turns a
compute number into a wall-clock number. Prints JSON.
"""

import json
import os
import sys
import time

from app.services import checkin as checkin_service
from app.services.checkin import CheckinService


def main() -> int:
    latency = int(os.getenv("LOAD_EMAIL_LATENCY_MS", "0")) / 1000
    sent = {"emails": 0, "pushes": 0}

    def fake_email(**kw):
        if latency:
            time.sleep(latency)
        sent["emails"] += 1
        return "brevo"

    def fake_push(sub, **kw):
        sent["pushes"] += 1
        return True

    checkin_service.send_email = fake_email
    checkin_service.send_push = fake_push

    started = time.perf_counter()
    ran = CheckinService().run_due_alerts_once()
    elapsed = time.perf_counter() - started
    json.dump(
        {
            "ran": ran,
            "seconds": round(elapsed, 2),
            "emails": sent["emails"],
            "pushes": sent["pushes"],
            "email_latency_ms": int(latency * 1000),
            "alerts_per_second": round(sent["emails"] / elapsed, 1) if elapsed else None,
        },
        sys.stdout,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
