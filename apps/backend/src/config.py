from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

KillSwitch = Literal[
    "DEV_SMS_LOG_TO_STDOUT",
    "DEV_SKIP_OTP_VERIFY",
    "DEV_AUTO_SEED",
    "DEV_EXCEL_ALWAYS_FRESH",
]

_KILL_SWITCHES: tuple[KillSwitch, ...] = (
    "DEV_SMS_LOG_TO_STDOUT",
    "DEV_SKIP_OTP_VERIFY",
    "DEV_AUTO_SEED",
    "DEV_EXCEL_ALWAYS_FRESH",
)

_REQUIRED_WHATSAPP_VARS = (
    "TWILIO_WHATSAPP_ACCOUNT_SID",
    "TWILIO_WHATSAPP_AUTH_TOKEN",
    "TWILIO_WHATSAPP_FROM",
    "TWILIO_WHATSAPP_WEBHOOK_SECRET",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    NODE_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["debug", "info", "warn", "error"] = "info"
    APP_TIMEZONE: str = "Asia/Karachi"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT_SECONDS: int = 30

    QDRANT_URL: str
    QDRANT_API_KEY: str

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT_SECONDS: int = 15
    GROQ_FALLBACK_MODEL: str = "llama-3.1-70b-versatile"

    COHERE_API_KEY: str
    COHERE_EMBEDDING_MODEL: str = "embed-multilingual-v3.0"
    COHERE_INPUT_TYPE_INGEST: str = "search_document"
    COHERE_INPUT_TYPE_QUERY: str = "search_query"

    FEATURE_WHATSAPP: bool = False
    TWILIO_WHATSAPP_ACCOUNT_SID: str = ""
    TWILIO_WHATSAPP_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    TWILIO_WHATSAPP_WEBHOOK_SECRET: str = ""

    BETTER_AUTH_SECRET: str
    SESSION_MAX_AGE_HOURS: int = 168

    OTP_TTL_SECONDS: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    DEV_SMS_LOG_TO_STDOUT: bool = True

    RATE_LIMIT_OTP_PER_HOUR: int = 3
    RATE_LIMIT_DASHBOARD_PER_MIN: int = 120
    RATE_LIMIT_WIDGET_INBOUND_PER_MIN: int = 30
    RATE_LIMIT_WIDGET_OUTBOUND_PER_MIN: int = 60

    WIDGET_ALLOWED_ORIGINS: str = "http://localhost:3000"

    FEATURE_PAYMENT_TOGGLE: bool = False
    FEATURE_AUDIT_FLAG: bool = True

    LOG_FORMAT: Literal["json", "pretty"] = "json"
    LOG_FILE: str | None = "./logs/backend.log"
    REQUEST_ID_HEADER: str = "X-Request-ID"

    DEV_SKIP_OTP_VERIFY: bool = False
    DEV_AUTO_SEED: bool = True
    DEV_EXCEL_ALWAYS_FRESH: bool = True

    @property
    def widget_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.WIDGET_ALLOWED_ORIGINS.split(",")]


def check_kill_switches(settings: Settings) -> None:
    if settings.NODE_ENV != "production":
        return
    for kill_switch in _KILL_SWITCHES:
        if getattr(settings, kill_switch):
            raise RuntimeError(f"{kill_switch} must be false in production")


def check_whatsapp_guard(settings: Settings) -> None:
    if not settings.FEATURE_WHATSAPP:
        return
    missing = [name for name in _REQUIRED_WHATSAPP_VARS if not getattr(settings, name)]
    if missing:
        raise RuntimeError(f"FEATURE_WHATSAPP=true requires: {missing}")


settings = Settings()
check_kill_switches(settings)
check_whatsapp_guard(settings)
