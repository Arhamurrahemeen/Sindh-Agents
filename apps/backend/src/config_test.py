import pytest

from src.config import Settings, check_kill_switches, check_whatsapp_guard

_REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@host/db",
    "DATABASE_URL_SYNC": "postgresql://u:p@host/db",
    "QDRANT_URL": "https://example.qdrant.io",
    "QDRANT_API_KEY": "key",
    "GROQ_API_KEY": "key",
    "COHERE_API_KEY": "key",
    "BETTER_AUTH_SECRET": "secret",
}


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})  # type: ignore[arg-type]


def test_kill_switch_blocks_production_startup() -> None:
    settings = _settings(
        NODE_ENV="production",
        DEV_SMS_LOG_TO_STDOUT=False,
        DEV_SKIP_OTP_VERIFY=False,
        DEV_AUTO_SEED=True,
        DEV_EXCEL_ALWAYS_FRESH=False,
    )
    with pytest.raises(RuntimeError, match="DEV_AUTO_SEED"):
        check_kill_switches(settings)


def test_kill_switch_allows_production_when_all_false() -> None:
    settings = _settings(
        NODE_ENV="production",
        DEV_SMS_LOG_TO_STDOUT=False,
        DEV_SKIP_OTP_VERIFY=False,
        DEV_AUTO_SEED=False,
        DEV_EXCEL_ALWAYS_FRESH=False,
    )
    check_kill_switches(settings)  # does not raise


def test_kill_switch_ignored_outside_production() -> None:
    settings = _settings(NODE_ENV="development", DEV_AUTO_SEED=True)
    check_kill_switches(settings)  # does not raise


def test_whatsapp_guard_blocks_when_creds_missing() -> None:
    settings = _settings(FEATURE_WHATSAPP=True)
    with pytest.raises(RuntimeError, match="FEATURE_WHATSAPP"):
        check_whatsapp_guard(settings)


def test_whatsapp_guard_passes_when_creds_present() -> None:
    settings = _settings(
        FEATURE_WHATSAPP=True,
        TWILIO_WHATSAPP_ACCOUNT_SID="AC1",
        TWILIO_WHATSAPP_AUTH_TOKEN="tok",
        TWILIO_WHATSAPP_FROM="whatsapp:+1",
        TWILIO_WHATSAPP_WEBHOOK_SECRET="sec",
    )
    check_whatsapp_guard(settings)  # does not raise


def test_whatsapp_guard_skipped_when_flag_off() -> None:
    settings = _settings(FEATURE_WHATSAPP=False)
    check_whatsapp_guard(settings)  # does not raise
