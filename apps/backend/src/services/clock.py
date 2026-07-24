from datetime import datetime
from zoneinfo import ZoneInfo

KARACHI_TZ = ZoneInfo("Asia/Karachi")


def now_in_karachi() -> datetime:
    return datetime.now(KARACHI_TZ)
