import logging

from src.config import settings

logger = logging.getLogger(__name__)


async def send_otp_sms(phone: str, otp: str, expires_in_seconds: int) -> None:
    if settings.DEV_SMS_LOG_TO_STDOUT:
        logger.info("DEV_OTP: phone=%s otp=%s expires_in=%ss", phone, otp, expires_in_seconds)
        return

    from twilio.rest import Client  # ponytail: imported lazily, only needed off the dev path

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        to=phone,
        from_=settings.TWILIO_FROM_NUMBER,
        body=f"Sindh Agents OTP: {otp} (expires in {expires_in_seconds // 60} min)",
    )
