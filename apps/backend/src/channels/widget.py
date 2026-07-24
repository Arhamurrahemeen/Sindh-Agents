class WidgetChannel:
    channel_name = "widget"

    async def send(self, *, conversation_id: str, text: str) -> None:
        # Widget "delivery" is the messages row itself — AuditRepository already
        # wrote it (same transaction as the audit entry, CLAUDE.md §7.3). The
        # buyer's long-poll on /api/widget/outbound reads that row directly.
        # This method exists so the channel swap to WhatsApp (P6) is a matter of
        # resolve_channel() picking a different implementation, not a rewrite —
        # CLAUDE.md §7.5's three disciplines.
        pass
