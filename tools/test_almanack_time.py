#!/usr/bin/env python3
"""Regression tests for Star Almanack canonical time handling."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from almanack_time import (
    AstroInstant,
    datetime_to_jd_utc,
    interpolate_instant,
    jd_tdb_to_jd_utc,
    jd_utc_to_jd_tdb,
)


class AlmanackTimeTests(unittest.TestCase):
    def test_jd_utc_tdb_round_trip(self):
        jd_utc = 2461111.5
        offset = 69.184
        jd_tdb = jd_utc_to_jd_tdb(jd_utc, offset)
        self.assertAlmostEqual(jd_tdb_to_jd_utc(jd_tdb, offset), jd_utc, places=12)

    def test_horizons_sample_preserves_canonical_jdtb(self):
        jd_utc = 2461111.5
        offset = 69.184
        instant = AstroInstant.from_horizons_utc(jd_utc, offset)
        self.assertAlmostEqual(instant.jd_tdb, jd_utc + offset / 86400.0, places=12)
        self.assertAlmostEqual(instant.jd_utc, jd_utc, places=12)

    def test_midnight_rounding_moves_date_and_time_together(self):
        source = datetime(2026, 3, 3, 23, 59, 59, 600000, tzinfo=timezone.utc)
        instant = AstroInstant.from_horizons_utc(
            datetime_to_jd_utc(source), 69.184
        )
        published = instant.publication_utc()
        self.assertEqual(published, datetime(2026, 3, 4, 0, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(instant.publication_date().isoformat(), "2026-03-04")
        self.assertEqual(instant.publication_time_text(), "00:00:00 UTC")

    def test_rounding_before_midnight_stays_on_same_date(self):
        source = datetime(2026, 3, 3, 23, 59, 59, 400000, tzinfo=timezone.utc)
        instant = AstroInstant.from_horizons_utc(
            datetime_to_jd_utc(source), 69.184
        )
        self.assertEqual(instant.publication_date().isoformat(), "2026-03-03")
        self.assertEqual(instant.publication_time_text(), "23:59:59 UTC")

    def test_pre_unix_epoch_rounding_is_symmetric(self):
        source = datetime(1969, 12, 31, 23, 59, 58, 600000, tzinfo=timezone.utc)
        instant = AstroInstant.from_horizons_utc(datetime_to_jd_utc(source), 0.0)
        self.assertEqual(
            instant.publication_utc(),
            datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(instant.publication_date().isoformat(), "1969-12-31")
        self.assertEqual(instant.publication_time_text(), "23:59:59 UTC")

    def test_pre_unix_midnight_carry_moves_date_and_time_together(self):
        source = datetime(1969, 12, 31, 23, 59, 59, 600000, tzinfo=timezone.utc)
        instant = AstroInstant.from_horizons_utc(datetime_to_jd_utc(source), 0.0)
        self.assertEqual(
            instant.publication_utc(), datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(instant.publication_date().isoformat(), "1970-01-01")
        self.assertEqual(instant.publication_time_text(), "00:00:00 UTC")

    def test_interpolation_is_in_jdtb(self):
        a = AstroInstant(2461111.0, 69.184)
        b = AstroInstant(2461112.0, 69.186)
        mid = interpolate_instant(a, b, 0.5)
        self.assertAlmostEqual(mid.jd_tdb, 2461111.5, places=12)
        self.assertAlmostEqual(mid.tdb_minus_utc_seconds, 69.185, places=12)


if __name__ == "__main__":
    unittest.main()
