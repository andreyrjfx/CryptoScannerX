import time

from app.main import format_time_until


def test_returns_dash_for_none():
    assert format_time_until(None) == "—"


def test_returns_dash_for_zero():
    assert format_time_until(0) == "—"


def test_returns_dash_for_past_time():
    past_ms = int((time.time() - 3600) * 1000)
    assert format_time_until(past_ms) == "—"


def test_formats_hours_and_minutes():
    # +30 секунд запаса, чтобы не попасть на границу минуты из-за времени
    # выполнения теста между вычислением future_ms и вызовом format_time_until
    future_ms = int((time.time() + 3 * 3600 + 25 * 60 + 30) * 1000)
    result = format_time_until(future_ms)
    assert result == "3h25m"


def test_formats_less_than_one_hour():
    future_ms = int((time.time() + 5 * 60 + 30) * 1000)
    result = format_time_until(future_ms)
    assert result == "0h05m"
