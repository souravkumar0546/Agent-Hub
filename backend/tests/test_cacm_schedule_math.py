"""Pure-function tests for schedule next-run math."""
from datetime import datetime, timezone

import pytest

from app.agents.cacm.schedule_math import compute_next_run_at


def _utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_daily_rolls_to_next_day_when_time_already_passed():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("daily", "09:00", now=now)
    assert nxt == _utc(2026, 5, 9, 9, 0)


def test_daily_uses_today_when_time_not_yet_passed():
    now = _utc(2026, 5, 8, 8, 0)
    nxt = compute_next_run_at("daily", "09:00", now=now)
    assert nxt == _utc(2026, 5, 8, 9, 0)


def test_weekly_advances_seven_days():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("weekly", "09:00", now=now)
    assert nxt == _utc(2026, 5, 15, 9, 0)


def test_monthly_advances_one_calendar_month():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("monthly", "09:00", now=now)
    assert nxt == _utc(2026, 6, 8, 9, 0)


def test_monthly_clamps_to_last_day():
    now = _utc(2026, 1, 31, 10, 0)
    nxt = compute_next_run_at("monthly", "09:00", now=now)
    assert nxt == _utc(2026, 2, 28, 9, 0)


def test_quarterly_adds_three_months():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("quarterly", "09:00", now=now)
    assert nxt == _utc(2026, 8, 8, 9, 0)


def test_half_yearly_adds_six_months():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("half_yearly", "09:00", now=now)
    assert nxt == _utc(2026, 11, 8, 9, 0)


def test_annually_adds_one_year():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("annually", "09:00", now=now)
    assert nxt == _utc(2027, 5, 8, 9, 0)


def test_annually_leap_day_clamps_to_feb28():
    now = _utc(2024, 2, 29, 10, 0)
    nxt = compute_next_run_at("annually", "09:00", now=now)
    assert nxt == _utc(2025, 2, 28, 9, 0)


def test_unknown_frequency_raises_value_error():
    now = _utc(2026, 5, 8, 10, 0)
    with pytest.raises(ValueError):
        compute_next_run_at("hourly", "09:00", now=now)


def test_invalid_time_of_day_raises_value_error():
    now = _utc(2026, 5, 8, 10, 0)
    with pytest.raises(ValueError):
        compute_next_run_at("daily", "9am", now=now)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        compute_next_run_at("daily", "09:00", now=datetime(2026, 5, 8, 10, 0))
