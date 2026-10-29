"""Station direction and completeness against independent daily JPL samples."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from skyfield.framelib import ecliptic_frame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from calculate_planetary_events import station_events
from star_almanack_ephemeris import StarAlmanackEphemeris
from almanack_calendar import CalendarEvent, get_event_records, set_events
from build_seasonal_calendar import event_allowed
import update_planetary_events as updater


class PlanetaryStationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = StarAlmanackEphemeris()
        # Mars starts its 2024–2025 retrograde in December 2024.
        cls.start = cls.engine.ts.utc(2024, 12, 1)
        cls.stop = cls.engine.ts.utc(2026, 1, 1)
        cls.events = station_events(cls.engine, cls.start, cls.stop)

    def test_all_seven_planets_and_both_directions(self):
        for planet in updater.PLANETS:
            kinds = {e["kind"] for e in self.events if e["planet"] == planet}
            self.assertEqual(kinds, {"retrograde station", "direct station"}, planet)

    def test_daily_longitude_turns_match_every_station(self):
        # Independent one-day displacements, with angular unwrap, count all
        # direction reversals (including planets crossing zero longitude).
        times = self.engine.ts.tt_jd(np.arange(self.start.tt - 1, self.stop.tt + 2))
        for planet in updater.PLANETS:
            body = self.engine.bodies[planet.lower()]
            position = self.engine.earth.at(times).observe(body).apparent()
            longitude = position.frame_latlon(ecliptic_frame)[1].radians
            displacement = np.diff(np.unwrap(longitude))
            turns = np.flatnonzero(np.sign(displacement[1:]) != np.sign(displacement[:-1]))
            events = [e for e in self.events if e["planet"] == planet]
            self.assertEqual(len(events), len(turns), planet)
            for event in events:
                instant = dt.datetime.fromisoformat(event["utc"].replace("Z", "+00:00"))
                t = self.engine.ts.from_datetime(instant)
                self.assertTrue(any(abs(float(times[i + 1].tt - t.tt)) < 1 for i in turns))
                # Wider samples verify the meaning of each label without using
                # the calculator's derivative or its search predicate.
                around = self.engine.ts.tt_jd(t.tt + np.array([-1, -.5, .5, 1]))
                lon = self.engine.earth.at(around).observe(body).apparent().frame_latlon(ecliptic_frame)[1].radians
                before, after = np.diff(np.unwrap(lon))[[0, 2]]
                if event["kind"] == "retrograde station":
                    self.assertGreater(before, 0)
                    self.assertLess(after, 0)
                else:
                    self.assertLess(before, 0)
                    self.assertGreater(after, 0)

    def test_calendar_insertion_preserves_entries_and_is_idempotent(self):
        event = next(e for e in self.events if e["utc"] >= "2025-01-01")
        day = dt.date.fromisoformat(event["utc"][:10])
        year, week, _ = day.isocalendar()
        source = updater.week_index(year, week).read_text()
        sentinel = CalendarEvent("Preserved target", fixed_object_id=123)
        source, found = set_events(source, day, [sentinel])
        self.assertTrue(found)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "index.html"
            path.write_text(source)
            data = Path(folder) / "events.json"
            data.write_text(json.dumps({"events": [event]}))
            events = updater.load_events(data)
            with patch.object(updater, "week_index", return_value=path):
                self.assertEqual(updater.update(events), [path])
                self.assertEqual(updater.update(events), [])
            records = get_event_records(path.read_text(), day)
            self.assertEqual(records[0], sentinel)
            self.assertIn(event["kind"], records[-1].html)
            self.assertTrue(event_allowed(records[-1].html))


if __name__ == "__main__":
    unittest.main()
