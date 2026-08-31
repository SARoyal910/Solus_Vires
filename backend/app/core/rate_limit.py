import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_MAX_TRACKED_KEYS = 10_000


class RateLimiter:
    """In-process sliding-window rate limiter, keyed by client IP.

    Single-process only - matches this app's single-uvicorn-worker deployment
    (see backend/Dockerfile). Move to a shared store (e.g. Redis) before
    scaling to multiple workers/instances, since each process would otherwise
    track its own counters and the effective limit would multiply silently.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        # Set by nginx from $remote_addr (nginx/conf.d/default.conf), which
        # always overwrites any client-supplied header of the same name -
        # safe to trust when the app is reached through that proxy.
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

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
