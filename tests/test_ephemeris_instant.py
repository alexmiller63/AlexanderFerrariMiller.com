"""Regression checks for date-only and timezone-aware ephemeris sampling."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from star_almanack_ephemeris import StarAlmanackEphemeris


class TimeCaptured(Exception):
    pass


def capture_time(value):
    engine = object.__new__(StarAlmanackEphemeris)
    engine.ts = Mock()
    engine.ts.utc.side_effect = TimeCaptured
    engine.ts.from_datetime.side_effect = TimeCaptured
    with pytest.raises(TimeCaptured):
        engine.sample("sun", value)
    return engine.ts


def test_date_only_preserves_midnight_utc_path():
    ts = capture_time(date(2026, 10, 5))
    ts.utc.assert_called_once_with(2026, 10, 5, 0, 0, 0)
    ts.from_datetime.assert_not_called()


def test_aware_utc_datetime_uses_exact_instant():
    instant = datetime(2026, 10, 5, 13, 14, 15, tzinfo=timezone.utc)
    ts = capture_time(instant)
    ts.from_datetime.assert_called_once_with(instant)
    ts.utc.assert_not_called()


def test_offset_datetime_is_converted_to_utc():
    local = datetime(2026, 10, 5, 8, 14, 15, tzinfo=timezone(timedelta(hours=-5)))
    ts = capture_time(local)
    ts.from_datetime.assert_called_once_with(datetime(2026, 10, 5, 13, 14, 15, tzinfo=timezone.utc))


def test_naive_datetime_is_rejected():
    engine = object.__new__(StarAlmanackEphemeris)
    engine.ts = Mock()
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.sample("sun", datetime(2026, 10, 5, 13, 14))
    engine.ts.utc.assert_not_called()
    engine.ts.from_datetime.assert_not_called()
