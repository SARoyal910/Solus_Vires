import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import contact, health
from .core.config import get_settings
from .core.middleware import add_security_headers


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
    )
    app.middleware("http")(add_security_headers)
    app.include_router(health.router)
    app.include_router(contact.router)

    if settings.site_dir.exists():
        app.mount("/", StaticFiles(directory=settings.site_dir, html=True), name="site")

    return app


app = create_app()
