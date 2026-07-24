import time
from collections import defaultdict

# ponytail: in-process sliding-window counter, not a shared store — fine for a
# single-worker hackathon deploy, resets on restart, doesn't span workers.
# Move to Redis/Postgres-backed counting if the backend ever runs >1 worker.
_windows: dict[str, list[float]] = defaultdict(list)


def is_allowed(key: str, limit: int, window_seconds: float = 60.0) -> bool:
    now = time.monotonic()
    timestamps = _windows[key]
    cutoff = now - window_seconds
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    return True
