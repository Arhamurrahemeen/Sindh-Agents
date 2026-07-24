import logging

logger = logging.getLogger(__name__)


class WhatsAppChannelStub:
    channel_name = "whatsapp"

    async def send(self, *, conversation_id: str, text: str) -> None:
        # CLAUDE.md §7.5 — stub exists from PR #1 so the demo-day flip to
        # Twilio is a swap, not a first-time interface design.
        logger.info("whatsapp_stub_send conversation_id=%s text=%s", conversation_id, text)
