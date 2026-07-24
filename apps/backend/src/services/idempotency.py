import time

# ponytail: in-process cache, not shared/persistent — same single-worker caveat
# as rate_limit.py. A restart forgets in-flight idempotency keys; acceptable at
# hackathon scale, revisit if the backend ever runs >1 worker or needs to
# survive restarts mid-24h-window.
_TTL_SECONDS = 24 * 3600
_cache: dict[str, tuple[str, float]] = {}


def get_cached(key: str) -> str | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    message_id, stored_at = entry
    if time.monotonic() - stored_at > _TTL_SECONDS:
        del _cache[key]
        return None
    return message_id


def store(key: str, message_id: str) -> None:
    _cache[key] = (message_id, time.monotonic())
