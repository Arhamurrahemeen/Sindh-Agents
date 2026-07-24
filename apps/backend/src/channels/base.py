from typing import Protocol

from src.config import settings


class OutboundChannel(Protocol):
    channel_name: str

    async def send(self, *, conversation_id: str, text: str) -> None: ...


def resolve_channel(channel_name: str) -> "OutboundChannel":
    from src.channels.whatsapp_stub import WhatsAppChannelStub
    from src.channels.widget import WidgetChannel

    if channel_name == "whatsapp":
        if not settings.FEATURE_WHATSAPP:
            raise ValueError("channel='whatsapp' requested but FEATURE_WHATSAPP is false")
        return WhatsAppChannelStub()
    return WidgetChannel()
