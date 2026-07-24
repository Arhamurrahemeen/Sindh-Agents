from datetime import date
from typing import Literal

from pydantic import BaseModel

from src.services.clock import now_in_karachi
from src.tools.types import ToolContext, ToolSuccess

_WEEKDAY_NAMES: tuple[
    Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], ...
] = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

FRIDAY = 4
SATURDAY = 5


class GetCurrentDateInput(BaseModel):
    """No inputs. Always returns Asia/Karachi 'now'."""


class CurrentDate(BaseModel):
    date: date
    day_of_week: Literal[
        "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
    ]
    is_business_day: bool
    hijri_date: str | None
    current_time_hhmm: str


GetCurrentDateOutput = ToolSuccess[CurrentDate]


async def get_current_date(
    inputs: GetCurrentDateInput, context: ToolContext
) -> GetCurrentDateOutput:
    now = now_in_karachi()
    return ToolSuccess[CurrentDate](
        data=CurrentDate(
            date=now.date(),
            day_of_week=_WEEKDAY_NAMES[now.weekday()],
            is_business_day=now.weekday() not in (FRIDAY, SATURDAY),
            hijri_date=None,
            current_time_hhmm=now.strftime("%H:%M"),
        )
    )
