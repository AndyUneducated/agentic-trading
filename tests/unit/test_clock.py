from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.clock import ManualClock, SystemClock


def test_manual_clock_advance_and_set() -> None:
    clock = ManualClock(datetime(2026, 1, 1, tzinfo=UTC))
    assert clock.now() == datetime(2026, 1, 1, tzinfo=UTC)
    clock.advance(timedelta(days=1))
    assert clock.now() == datetime(2026, 1, 2, tzinfo=UTC)
    clock.set(datetime(2026, 2, 1, tzinfo=UTC))
    assert clock.now().month == 2


def test_system_clock_is_tz_aware() -> None:
    assert SystemClock().now().tzinfo is not None
