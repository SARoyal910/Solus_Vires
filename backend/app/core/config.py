import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    contact_sink: str
    max_contact_message_length: int
    site_dir: Path
    database_url: str
    session_cookie_secure: bool
    session_ttl_days: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Solus Vires API"),
        environment=os.getenv("APP_ENV", "development"),
        contact_sink=os.getenv("CONTACT_SINK", "console"),
        max_contact_message_length=int(os.getenv("MAX_CONTACT_MESSAGE_LENGTH", "3000")),
        site_dir=Path(os.getenv("SITE_DIR", Path(__file__).resolve().parents[3] / "html")),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://solusvires:solusvires@localhost:5432/solusvires",
        ),
        session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        session_ttl_days=int(os.getenv("SESSION_TTL_DAYS", "14")),
    )
