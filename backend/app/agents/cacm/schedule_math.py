"""Pure helpers for CACM schedule math.

Schedules use a "relative-to-creation" anchor — there is no day-of-week or
day-of-month picker in the UI. `compute_next_run_at` therefore takes only
`(frequency, time_of_day, now)` and returns the next UTC datetime when the
schedule should fire.

`now` MUST be timezone-aware (UTC). The returned value preserves the
day-of-month from `now` for monthly+ frequencies, clamping to the last
valid day of the target month (e.g. Jan 31 + 1 month → Feb 28/29).
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Final


_FREQUENCIES: Final[set[str]] = {
    "daily", "weekly", "monthly", "quarterly", "half_yearly", "annually",
}


def _parse_time(s: str) -> tuple[int, int]:
    """Parse a strict HH:MM string. Raises ValueError on bad input."""
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        raise ValueError(f"time_of_day must be HH:MM, got {s!r}")
    try:
        hh = int(s[:2])
        mm = int(s[3:])
    except ValueError as e:
        raise ValueError(f"time_of_day must be HH:MM digits, got {s!r}") from e
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"time_of_day out of range, got {s!r}")
    return hh, mm


def _add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def compute_next_run_at(
    frequency: str,
    time_of_day: str,
    *,
    now: datetime,
) -> datetime:
    if frequency not in _FREQUENCIES:
        raise ValueError(f"unknown frequency {frequency!r}")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (UTC)")
    hh, mm = _parse_time(time_of_day)

    anchor = now.astimezone(timezone.utc).replace(
        hour=hh, minute=mm, second=0, microsecond=0,
    )

    if anchor > now:
        return anchor

    if frequency == "daily":
        return anchor + timedelta(days=1)
    if frequency == "weekly":
        return anchor + timedelta(days=7)
    if frequency == "monthly":
        return _add_months(anchor, 1)
    if frequency == "quarterly":
        return _add_months(anchor, 3)
    if frequency == "half_yearly":
        return _add_months(anchor, 6)
    return _add_months(anchor, 12)
