import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import auth, checkin, contact, evidence, health
from .core.config import get_settings
from .core.middleware import add_security_headers
from .services.checkin import CheckinService

logger = logging.getLogger("solusvires.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.checkin_token_secret:
        logger.warning(
            "CHECKIN_TOKEN_SECRET is not set - check-in invite links are insecure until it is."
        )
    alert_task = asyncio.create_task(CheckinService().run_alert_loop())
    try:
        yield
    finally:
        alert_task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        description="Backend services for Solus Vires public safety resources.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(add_security_headers)
    app.include_router(health.router)
    app.include_router(contact.router)
    app.include_router(auth.router)
    app.include_router(evidence.router)
    app.include_router(checkin.router)

    if settings.site_dir.exists():
        app.mount("/", StaticFiles(directory=settings.site_dir, html=True), name="site")

    return app


app = create_app()
