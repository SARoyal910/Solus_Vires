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
    public_base_url: str
    vapid_public_key: str
    vapid_private_key: str
    vapid_subject: str
    brevo_api_key: str
    brevo_sender_email: str
    brevo_sender_name: str
    checkin_alert_check_seconds: int
    checkin_alert_repeat_hours: int
    checkin_token_secret: str
    trust_proxy_headers: bool
    beta_signups_open: bool
    beta_invite_codes: tuple[str, ...]


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
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
        vapid_public_key=os.getenv("VAPID_PUBLIC_KEY", ""),
        vapid_private_key=os.getenv("VAPID_PRIVATE_KEY", ""),
        vapid_subject=os.getenv("VAPID_SUBJECT", "mailto:admin@example.com"),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        brevo_sender_email=os.getenv("BREVO_SENDER_EMAIL", "no-reply@example.com"),
        brevo_sender_name=os.getenv("BREVO_SENDER_NAME", "Solus Vires"),
        checkin_alert_check_seconds=int(os.getenv("CHECKIN_ALERT_CHECK_SECONDS", "300")),
        checkin_alert_repeat_hours=int(os.getenv("CHECKIN_ALERT_REPEAT_HOURS", "6")),
        checkin_token_secret=os.getenv("CHECKIN_TOKEN_SECRET", ""),
        trust_proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true",
        # Closed by default: until legal and advocacy review are done, new
        # accounts need an invite code (engineering review H6).
        beta_signups_open=os.getenv("BETA_SIGNUPS_ENABLED", "false").lower() == "true",
        beta_invite_codes=tuple(
            code.strip() for code in os.getenv("BETA_INVITE_CODES", "").split(",") if code.strip()
        ),
    )
