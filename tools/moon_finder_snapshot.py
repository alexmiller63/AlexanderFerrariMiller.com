"""Monday-00:00-UTC lunar disk geometry from the cached Almanack ephemeris."""
from datetime import date
from functools import lru_cache
import math

from star_almanack_ephemeris import StarAlmanackEphemeris

# NASA Moon Fact Sheet: volumetric mean radius, km.
# https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html
MOON_RADIUS_KM = 1737.4


@lru_cache(maxsize=128)
def lunar_disk_snapshot(year: int, week: int) -> dict:
    day = date.fromisocalendar(year, week, 1)
    model = StarAlmanackEphemeris()
    t = model.ts.utc(day.year, day.month, day.day, 0, 0, 0)
    earth = model.earth.at(t)
    moon = earth.observe(model.bodies["moon"]).apparent()
    sun = earth.observe(model.sun).apparent()
    ra, dec, distance = moon.radec()
    sun_ra, sun_dec, _ = sun.radec()
    dra = sun_ra.radians - ra.radians
    # Position angle measured from celestial north towards east.
    bright_limb = math.atan2(
        math.sin(dra),
        math.cos(dec.radians) * math.tan(sun_dec.radians)
        - math.sin(dec.radians) * math.cos(dra),
    )
    phase = float(moon.phase_angle(model.sun).degrees)
    return {
        "snapshot_utc": f"{day.isoformat()}T00:00:00Z",
        "angular_diameter_deg": math.degrees(2 * math.asin(MOON_RADIUS_KM / float(distance.km))),
        "phase_angle_deg": phase,
        "illuminated_fraction": float(moon.fraction_illuminated(model.sun)),
        "bright_limb_position_angle_deg": math.degrees(bright_limb) % 360,
        "distance_km": float(distance.km),
    }
