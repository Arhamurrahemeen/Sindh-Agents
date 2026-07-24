PREVIEW_LIMIT = 60


def truncate_preview(text: str, limit: int = PREVIEW_LIMIT) -> str:
    # api-contract.md §2.1 — word-safe cut (trim to last space) so we never split
    # a token like "12,345" mid-number; single "…" char, not three dots.
    if len(text) <= limit:
        return text

    window = text[:limit]
    last_space = window.rfind(" ")
    truncated = window[:last_space] if last_space != -1 else window
    return truncated.rstrip() + "…"
