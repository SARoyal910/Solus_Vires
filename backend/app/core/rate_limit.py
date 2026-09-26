import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from .config import get_settings

_MAX_TRACKED_KEYS = 10_000


def client_ip(request: Request) -> str:
    """The address to rate-limit on.

    X-Real-IP is only honoured when TRUST_PROXY_HEADERS is on, which the Docker
    deployment sets because nginx always overwrites that header with the
    visitor's address (see nginx/snippets/cloudflare-realip.conf). A bare
    uvicorn leaves it off, so a client can't pick its own bucket by sending
    the header itself.
    """
    if get_settings().trust_proxy_headers:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """In-process sliding-window rate limiter, keyed by client IP.

    Single-process only - matches this app's single-uvicorn-worker deployment
    (see backend/Dockerfile). Move to a shared store (e.g. Redis) before
    scaling to multiple workers/instances, since each process would otherwise
    track its own counters and the effective limit would multiply silently.
    """

    instances: list["RateLimiter"] = []

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        RateLimiter.instances.append(self)

    def reset(self) -> None:
        """Forgets all tracked clients. Used by the test suite between tests."""
        self._hits.clear()

    def _client_ip(self, request: Request) -> str:
        return client_ip(request)

    def _sweep(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > self.window_seconds]
        for key in stale:
            del self._hits[key]

    def __call__(self, request: Request) -> None:
        now = time.monotonic()
        if len(self._hits) > _MAX_TRACKED_KEYS:
            self._sweep(now)

        hits = self._hits[self._client_ip(request)]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

        hits.append(now)
