import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    contact_sink: str
    max_contact_message_length: int
    contact_inbox_email: str
    contact_response_days: int
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
    checkin_alert_loop_enabled: bool
    checkin_alert_repeat_hours: int
    checkin_token_secret: str
    recovery_code_pepper: str
    trust_proxy_headers: bool
    operator_alert_email: str
    abuse_alert_threshold: int
    beta_signups_open: bool
    beta_invite_codes: tuple[str, ...]


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() == "true"


@lru_cache
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development")
    return Settings(
        app_name=os.getenv("APP_NAME", "Solus Vires API"),
        environment=environment,
        contact_sink=os.getenv("CONTACT_SINK", "console"),
        max_contact_message_length=int(os.getenv("MAX_CONTACT_MESSAGE_LENGTH", "3000")),
        # Where contact-form messages are emailed (decision D3). Empty = the
        # form is off and the page says so, rather than pretending to send.
        contact_inbox_email=os.getenv("CONTACT_INBOX_EMAIL", "").strip(),
        # The reply window the form promises. Keep it honest: one person reads these.
        contact_response_days=int(os.getenv("CONTACT_RESPONSE_DAYS", "7")),
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
        # On by default only in production, so a local uvicorn pointed at the
        # shared database doesn't run a second loop (review M1). The advisory
        # lock in the alert pass makes a second loop harmless anyway.
        checkin_alert_loop_enabled=_flag("CHECKIN_ALERT_LOOP_ENABLED", environment == "production"),
        checkin_alert_repeat_hours=int(os.getenv("CHECKIN_ALERT_REPEAT_HOURS", "6")),
        checkin_token_secret=os.getenv("CHECKIN_TOKEN_SECRET", ""),
        # Server-side key for recovery-code HMACs. Never change it once codes
        # exist: every code issued under the old value would stop working.
        recovery_code_pepper=os.getenv("RECOVERY_CODE_PEPPER", ""),
        trust_proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true",
        # Where operator-only notices go (abuse alerts). Empty = off.
        operator_alert_email=os.getenv("OPERATOR_ALERT_EMAIL", "").strip(),
        # 429s from one address within an hour before the operator is emailed.
        abuse_alert_threshold=int(os.getenv("ABUSE_ALERT_THRESHOLD", "50")),
        # Closed by default: until legal and advocacy review are done, new
        # accounts need an invite code (engineering review H6).
        beta_signups_open=os.getenv("BETA_SIGNUPS_ENABLED", "false").lower() == "true",
        beta_invite_codes=tuple(
            code.strip() for code in os.getenv("BETA_INVITE_CODES", "").split(",") if code.strip()
        ),
    )


# Passwords that ship in this repo's examples and defaults. A production
# database using one of them is as good as unprotected.
_DEFAULT_DB_PASSWORDS = frozenset({"", "solusvires", "postgres", "password", "test-only", "changeme"})


def _is_placeholder(value: str) -> bool:
    return not value.strip() or value.strip().startswith("replace-with")


def production_config_problems(settings: Settings) -> list[str]:
    """Why this configuration must not run in production; empty when it's fine (review M9).

    Only applies when APP_ENV=production. Messages name the setting, never its value.
    """
    if settings.environment != "production":
        return []
    problems = []
    if _is_placeholder(settings.checkin_token_secret):
        problems.append("CHECKIN_TOKEN_SECRET is empty or a placeholder: invite and alert links would be forgeable.")
    if _is_placeholder(settings.recovery_code_pepper):
        problems.append("RECOVERY_CODE_PEPPER is empty or a placeholder.")
    db_password = make_url(settings.database_url).password or ""
    env_password = os.getenv("POSTGRES_PASSWORD")
    for password in (db_password, env_password):
        if password is not None and (password in _DEFAULT_DB_PASSWORDS or _is_placeholder(password)):
            problems.append("The database password (POSTGRES_PASSWORD) is a default or a placeholder.")
            break
    return problems
