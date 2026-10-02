import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from .abuse_alert import abuse_monitor
from .rate_limit import client_ip


async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    response = await call_next(request)
    if response.status_code == 429:
        alert = abuse_monitor.record_429(client_ip(request), request.url.path)
        if alert is not None:
            # Off the request path: the refused client never waits on email.
            asyncio.get_running_loop().run_in_executor(None, abuse_monitor.send_alert, alert)
    response.headers["x-request-id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self)"

    if request.url.path.startswith(
        (
            "/contact",
            "/api/contact",
            "/api/auth",
            "/api/evidence",
            "/api/checkin",
            "/account.html",
            "/log.html",
            "/checkin.html",
            "/checkin-invite.html",
        )
    ):
        response.headers["Cache-Control"] = "no-store"

    return response
