"""Slows password guessing without letting anyone lock a survivor out.

The old rule locked an account for everyone after 8 failures, so anyone who
knew a username (an abuser, or a trusted contact who saw it on an invite)
could keep the survivor out of their own notes indefinitely (engineering
review H5). Failures are now counted per (client IP, username) pair and only
that pair has to wait, with the wait growing after each failure. The survivor
on their own device or network is unaffected, and a valid recovery code always
works.

In-process, like the rate limiter: single uvicorn worker only.
"""

import time
from dataclasses import dataclass

from fastapi import HTTPException, status

FREE_ATTEMPTS = 3
MAX_DELAY_SECONDS = 30
_FORGET_AFTER_SECONDS = 3600
_MAX_TRACKED_PAIRS = 10_000


def _now() -> float:
    return time.monotonic()


@dataclass
class _Failures:
    count: int
    last_at: float


def delay_for(failures: int) -> int:
    """Seconds a pair must wait after this many consecutive failures: 0,0,0,1,2,4,8,16,30,30…"""
    if failures < FREE_ATTEMPTS:
        return 0
    return min(2 ** (failures - FREE_ATTEMPTS), MAX_DELAY_SECONDS)


class LoginThrottle:
    def __init__(self) -> None:
        self._pairs: dict[tuple[str, str], _Failures] = {}

    @staticmethod
    def _key(ip: str, username: str) -> tuple[str, str]:
        return ip, username.lower()

    def _sweep(self, now: float) -> None:
        stale = [k for k, f in self._pairs.items() if now - f.last_at > _FORGET_AFTER_SECONDS]
        for key in stale:
            del self._pairs[key]

    def check(self, ip: str, username: str) -> None:
        """Raises 429 if this pair is still waiting out its delay."""
        failures = self._pairs.get(self._key(ip, username))
        if failures is None:
            return
        wait = failures.last_at + delay_for(failures.count) - _now()
        if wait > 0:
            seconds = max(1, round(wait))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Wait {seconds} seconds and try again.",
                headers={"Retry-After": str(seconds)},
            )

    def record_failure(self, ip: str, username: str) -> None:
        now = _now()
        if len(self._pairs) > _MAX_TRACKED_PAIRS:
            self._sweep(now)
        key = self._key(ip, username)
        previous = self._pairs.get(key)
        count = 1 if previous is None or now - previous.last_at > _FORGET_AFTER_SECONDS else previous.count + 1
        self._pairs[key] = _Failures(count=count, last_at=now)

    def record_success(self, ip: str, username: str) -> None:
        self._pairs.pop(self._key(ip, username), None)

    def forget_username(self, username: str) -> None:
        """After a recovery-code reset, no address should still be waiting on the old password."""
        name = username.lower()
        for key in [k for k in self._pairs if k[1] == name]:
            del self._pairs[key]

    def reset(self) -> None:
        self._pairs.clear()


login_throttle = LoginThrottle()
