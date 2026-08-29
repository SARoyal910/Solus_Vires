from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response


async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self)"

    if request.url.path.startswith(
        ("/contact", "/api/contact", "/api/auth", "/api/evidence", "/account.html", "/log.html")
    ):
        response.headers["Cache-Control"] = "no-store"

    return response
