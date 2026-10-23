"""Civil-day and horizon regressions; real SPKs are required for integration."""
import math
import unittest
from datetime import datetime, timedelta, timezone

from skyfield import almanac
from skyfield.api import wgs84

from generate_observer_ephemera import calculate, civil_day, horizon, horizon_crossings
from star_almanack_ephemeris import StarAlmanackEphemeris

UTC = timezone.utc


class ObserverTimeTests(unittest.TestCase):
    def test_dst_day_lengths(self):
        for month, day, hours in [(3, 8, 23), (11, 1, 25)]:
            instant = datetime(2026, month, day, 12, tzinfo=UTC)
            local, start, end = civil_day(instant, "America/Los_Angeles")
            self.assertEqual(local, instant.date())
            self.assertEqual((end - start).total_seconds(), hours * 3600)

    def test_instant_can_belong_to_previous_local_date(self):
        local, start, end = civil_day(datetime(2026, 10, 23, 2, tzinfo=UTC),
                                      "America/Los_Angeles")
        self.assertEqual(str(local), "2026-10-22")
        self.assertEqual(start.hour, 7)

    def test_midnight_crossing_once_and_end_excluded(self):
        day = datetime(2026, 1, 1, tzinfo=UTC)
        times = [day + timedelta(hours=i) for i in range(25)]
        # Cross at the start, interior sample, and next day's midnight.
        def offset(t):
            return math.sin((t - day).total_seconds() * math.pi / 43200)
        heights = [offset(t) for t in times]
        heights[0] = heights[12] = heights[24] = 0.0
        events = horizon_crossings(times, heights, offset)
        self.assertEqual(events, [("rise", day), ("set", times[12])])

    def test_lunar_threshold_includes_upper_limb_without_double_parallax(self):
        self.assertAlmostEqual(horizon("moon", 384400), -0.82562, places=4)
        self.assertAlmostEqual(horizon("sun", 149597870.7), -0.83312, places=4)
        self.assertAlmostEqual(horizon("mars", 1e8), -34 / 60)


class ObserverKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = StarAlmanackEphemeris()

    def test_report_and_independent_solar_event_search(self):
        instant = datetime(2026, 10, 22, 21, tzinfo=UTC)
        data = calculate(instant, 34.1083, -117.2898, 0,
                         "America/Los_Angeles", engine=self.engine)
        self.assertEqual(len(data["bodies"]), 11)
        self.assertNotIn("earth", [r["body"] for r in data["bodies"]])
        start = datetime.fromisoformat(data["rise_set_window_utc"]["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(data["rise_set_window_utc"]["end"].replace("Z", "+00:00"))
        for row in data["bodies"]:
            for event in row["rise_set"]["events"]:
                dt = datetime.fromisoformat(event["utc"].replace("Z", "+00:00"))
                self.assertTrue(start <= dt < end)
                self.assertEqual(event["local"][:10], data["rise_set_local_date"])
        # A separately implemented Skyfield discrete search uses a fixed standard
        # solar radius. Agreement within 10 seconds allows seasonal radius change.
        f = almanac.sunrise_sunset(self.engine.planets, wgs84.latlon(34.1083, -117.2898))
        ts = self.engine.ts
        times, up = almanac.find_discrete(ts.from_datetime(start), ts.from_datetime(end), f)
        events = data["bodies"][0]["rise_set"]["events"]
        self.assertEqual(len(events), len(times))
        for event, t, is_up in zip(events, times, up):
            self.assertEqual(event["type"], "rise" if is_up else "set")
            dt = datetime.fromisoformat(event["utc"].replace("Z", "+00:00"))
            self.assertLess(abs((dt - t.utc_datetime()).total_seconds()), 10)

    def test_polar_sun_does_not_invent_events(self):
        for month, state in [(6, "always above horizon"), (12, "always below horizon")]:
            data = calculate(datetime(2026, month, 21, 12, tzinfo=UTC), 89, 0, 0,
                             engine=self.engine)
            self.assertEqual(data["bodies"][0]["rise_set"], {"state": state, "events": []})


if __name__ == "__main__":
    unittest.main()
