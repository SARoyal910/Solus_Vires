"""Emails the operator once when one address keeps hitting rate limits (P2-F3).

Counts 429 responses per client address in memory over a sliding hour. When
one address reaches ABUSE_ALERT_THRESHOLD, the operator (OPERATOR_ALERT_EMAIL)
gets one email; that address won't trigger another for a day, and no more than
MAX_ALERTS_PER_DAY go out in total. Off when OPERATOR_ALERT_EMAIL is empty.

Addresses are never written to disk, the database, the logs, or the email:
the site keeps no IP history (decision D8), and an operator inbox is still a
record. The email says how many hits and on which paths, not from where.
In-process, like the rate limiter: single uvicorn worker only.
"""

import logging
import threading
import time
from collections import Counter, defaultdict, deque

from .config import get_settings
from .notifications import send_email

logger = logging.getLogger("solusvires.abuse")

WINDOW_SECONDS = 3600
REALERT_AFTER_SECONDS = 24 * 3600
MAX_ALERTS_PER_DAY = 5
_MAX_TRACKED = 10_000


def _now() -> float:
    return time.monotonic()


class AbuseMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[tuple[float, str]]] = defaultdict(deque)
        self._alerted_at: dict[str, float] = {}
        self._sent: deque[float] = deque()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._alerted_at.clear()
            self._sent.clear()

    def _sweep(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1][0] > WINDOW_SECONDS]:
            del self._hits[key]
        for key in [k for k, t in self._alerted_at.items() if now - t > REALERT_AFTER_SECONDS]:
            del self._alerted_at[key]

    def record_429(self, ip: str, path: str) -> str | None:
        """Notes one rate-limited response. Returns the email body when an alert is due, else None."""
        settings = get_settings()
        if not settings.operator_alert_email:
            return None
        now = _now()
        with self._lock:
            if len(self._hits) > _MAX_TRACKED:
                self._sweep(now)
            hits = self._hits[ip]
            hits.append((now, path))
            while hits and now - hits[0][0] > WINDOW_SECONDS:
                hits.popleft()
            if len(hits) < settings.abuse_alert_threshold:
                return None
            last = self._alerted_at.get(ip)
            if last is not None and now - last < REALERT_AFTER_SECONDS:
                return None
            while self._sent and now - self._sent[0] > 24 * 3600:
                self._sent.popleft()
            if len(self._sent) >= MAX_ALERTS_PER_DAY:
                return None
            self._alerted_at[ip] = now
            self._sent.append(now)
            paths = Counter(p for _, p in hits)
        return _email_html(len(hits), paths)

    def send_alert(self, html_content: str) -> None:
        settings = get_settings()
        sent = send_email(
            to_email=settings.operator_alert_email,
            to_name="Solus Vires operator",
            subject="Solus Vires: repeated rate-limit hits from one address",
            html_content=html_content,
        )
        logger.warning("abuse_alert_sent" if sent else "abuse_alert_send_failed")


def _email_html(count: int, paths: Counter) -> str:
    rows = "".join(f"<li>{path}: {n}</li>" for path, n in paths.most_common(10))
    return f"""
    <p><strong>One address was refused by the rate limits {count} times in the last hour.</strong></p>
    <ul>{rows}</ul>
    <p>The address itself isn't recorded or included here: the site keeps no IP history by design.
    The limits are already doing their job; this is a heads-up. If it keeps happening, consider a
    Cloudflare rate-limiting or firewall rule. You won't get another email about the same address
    for 24 hours, and at most {MAX_ALERTS_PER_DAY} of these a day.</p>
    """.strip()


abuse_monitor = AbuseMonitor()
