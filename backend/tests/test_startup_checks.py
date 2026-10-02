"""P2-A16: production refuses to start with secrets that would make it unsafe."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings, production_config_problems
from app.main import app

GOOD = {
    "APP_ENV": "production",
    "CHECKIN_TOKEN_SECRET": "a-real-long-random-secret",
    "RECOVERY_CODE_PEPPER": "another-real-long-random-secret",
    "DATABASE_URL": "postgresql+psycopg://solusvires:Xk3-long-random@db:5432/solusvires",
    "POSTGRES_PASSWORD": None,
    "CHECKIN_ALERT_LOOP_ENABLED": "false",
}


def test_good_production_config_has_no_problems(settings_env):
    settings_env(**GOOD)
    assert production_config_problems(get_settings()) == []


@pytest.mark.parametrize(
    "override, mentions",
    [
        ({"CHECKIN_TOKEN_SECRET": ""}, "CHECKIN_TOKEN_SECRET"),
        ({"CHECKIN_TOKEN_SECRET": "replace-with-a-long-random-secret"}, "CHECKIN_TOKEN_SECRET"),
        ({"RECOVERY_CODE_PEPPER": ""}, "RECOVERY_CODE_PEPPER"),
        ({"DATABASE_URL": "postgresql+psycopg://solusvires:solusvires@db:5432/solusvires"}, "POSTGRES_PASSWORD"),
        (
            {"DATABASE_URL": "postgresql+psycopg://solusvires:replace-with-a-long-random-password@db/solusvires"},
            "POSTGRES_PASSWORD",
        ),
        ({"POSTGRES_PASSWORD": "postgres"}, "POSTGRES_PASSWORD"),
    ],
)
def test_each_unsafe_setting_is_reported(settings_env, override, mentions):
    settings_env(**{**GOOD, **override})
    problems = production_config_problems(get_settings())
    assert len(problems) == 1 and mentions in problems[0]


def test_development_is_never_blocked(settings_env):
    settings_env(APP_ENV="development", CHECKIN_TOKEN_SECRET="", RECOVERY_CODE_PEPPER="")
    assert production_config_problems(get_settings()) == []


def test_app_refuses_to_start_in_production_with_an_empty_secret(settings_env):
    settings_env(**{**GOOD, "CHECKIN_TOKEN_SECRET": ""})
    with pytest.raises(RuntimeError, match="CHECKIN_TOKEN_SECRET"):
        with TestClient(app):
            pass


def test_app_starts_in_production_with_good_config(settings_env):
    settings_env(**GOOD)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
