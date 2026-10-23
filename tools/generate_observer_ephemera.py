#!/usr/bin/env python3
"""Topocentric ephemeris; numerical horizon crossings over an observer's civil day."""
import argparse
import html
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield.api import wgs84
from skyfield.framelib import ecliptic_frame
from star_almanack_ephemeris import StarAlmanackEphemeris

UTC = timezone.utc
BODIES = ("sun", "moon", "mercury", "venus", "mars", "ceres", "jupiter", "saturn",
          "uranus", "neptune", "pluto")


def stamp(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def horizon(body, distance_km):
    """Geometric centre altitude when the apparent upper limb meets the horizon.

    Topocentric positions already include lunar parallax. Apply standard
    34-arcminute refraction and the distance-dependent Sun/Moon semidiameter;
    do not apply a second, geocentric lunar parallax correction.
    """
    radius_km = {"sun": 695700.0, "moon": 1737.4}.get(body, 0.0)
    return -34.0 / 60.0 - math.degrees(math.asin(radius_km / distance_km))


def horizon_crossings(times, heights, offset):
    """Bisect sampled crossings in the half-open interval [start, end)."""
    events = []
    for i in range(len(times) - 1):
        fa, fb = heights[i], heights[i + 1]
        if fa == 0:
            # Include midnight; an interior exact root is handled only here.
            before = offset(times[i] - timedelta(seconds=1))
            after = offset(times[i] + timedelta(seconds=1))
            if (before < 0) == (after < 0):
                continue  # tangent, rather than a rise or set
            root = times[i]
            kind = "rise" if after > before else "set"
        elif fb == 0 or (fa < 0) == (fb < 0):
            continue  # next interval handles exact roots; end is excluded
        else:
            a, b = times[i], times[i + 1]
            kind = "rise" if fa < 0 else "set"
            for _ in range(20):
                m = a + (b - a) / 2
                fm = offset(m)
                if (fa < 0) != (fm < 0):
                    b = m
                else:
                    a, fa = m, fm
            root = a + (b - a) / 2
        events.append((kind, root))
    return events


def civil_day(instant, timezone_name):
    """Return the half-open UTC interval for the instant's local calendar date.

    Construct the next *local* midnight, rather than adding 24 hours in UTC:
    daylight-saving days can contain 23 or 25 hours.
    """
    if instant.tzinfo is None:
        raise ValueError("An explicit UTC offset is required")
    zone = ZoneInfo(timezone_name)
    local = instant.astimezone(zone)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local.date(), midnight.astimezone(UTC), (midnight + timedelta(days=1)).astimezone(UTC)


def calculate(instant, latitude, longitude, elevation, timezone_name="UTC", *, engine=None):
    if instant.tzinfo is None:
        raise ValueError("An explicit UTC offset is required")
    instant = instant.astimezone(UTC)
    if not 1900 <= instant.year <= 2099:
        raise ValueError("Current source kernels support 1900–2099, subject to boundary-date coverage")
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be −90 to +90")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be −180 to +180")
    if not math.isfinite(elevation) or not -500 <= elevation <= 10000:
        raise ValueError("Elevation must be −500 to 10,000 metres")
    local_date, day, end = civil_day(instant, timezone_name)
    zone = ZoneInfo(timezone_name)
    engine = engine or StarAlmanackEphemeris()
    # Light-time evaluation needs source data slightly before the reception
    # instant; fail clearly before computing any partial report at kernel edges.
    ceres = engine._body("ceres")
    try:
        for dt in (instant, day, end):
            engine.earth.at(engine.ts.from_datetime(dt)).observe(ceres)
    except ValueError as exc:
        raise ValueError("The requested instant or civil day exceeds Ceres source coverage; "
                         "choose a date farther inside 1900–2099") from exc
    observer = engine.earth + wgs84.latlon(latitude, longitude, elevation_m=elevation)
    # A closed sampling grid brackets events; only roots in [day, end) are published.
    steps = math.ceil((end - day).total_seconds() / 600)
    times = [min(day + timedelta(minutes=10 * i), end) for i in range(steps + 1)]
    results = []
    for body in BODIES:
        target = engine._body(body)

        def apparent(dt):
            return observer.at(engine.ts.from_datetime(dt)).observe(target).apparent()

        obj = apparent(instant)
        ra, dec, dist = obj.radec()
        lat, lon, _ = obj.frame_latlon(ecliptic_frame)
        alt, az, _ = obj.altaz()

        def offset(dt):
            position = apparent(dt)
            altitude, _, distance = position.altaz()
            return float(altitude.degrees) - horizon(body, float(distance.km))

        # The piecewise Ceres adapter accepts scalar instants; other SPKs support
        # a single vectorized sampling pass, reducing work on phones.
        if body == "ceres":
            heights = [offset(t) for t in times]
        else:
            samples = engine.ts.from_datetimes(times)
            altitude, _, distance = observer.at(samples).observe(target).apparent().altaz()
            heights = [float(x) - horizon(body, float(d))
                       for x, d in zip(altitude.degrees, distance.km)]
        events = []
        for kind, root in horizon_crossings(times, heights, offset):
            events.append({"type": kind, "utc": stamp(root),
                           "local": root.astimezone(zone).isoformat(timespec="seconds")})
        state = "crossings" if events else (
            "always above horizon" if all(v > 0 for v in heights) else
            "always below horizon" if all(v < 0 for v in heights) else "no crossing resolved")
        results.append({"body": body, "ra_hours": round(float(ra.hours), 8),
                        "dec_deg": round(float(dec.degrees), 7),
                        "ecliptic_longitude_deg": round(float(lon.degrees) % 360, 7),
                        "ecliptic_latitude_deg": round(float(lat.degrees), 7),
                        "distance_au": round(float(dist.au), 9),
                        "altitude_deg": round(float(alt.degrees), 6),
                        "azimuth_deg": round(float(az.degrees), 6),
                        "rise_set": {"state": state, "events": events}})
        print("COMPUTED", body, len(events), "horizon crossings", flush=True)
    data = {"instant_utc": stamp(instant), "rise_set_local_date": local_date.isoformat(),
            "timezone": timezone_name, "rise_set_window_utc": {"start": stamp(day), "end": stamp(end)},
            "observer": {"latitude": latitude, "longitude": longitude, "elevation_m": elevation},
            "source": "local DE440s and Ceres JPL/NAIF source SPKs via Skyfield",
            "precision": "provisional; atmospheric refraction, terrain, weather and grazing events not validated",
            "notes": ["Coordinates are topocentric apparent; RA/Dec use the ICRF axes.",
                      "Rise/set belong to the selected timezone's civil date, with DST applied.",
                      "Continuous positions are resampled and horizon crossings bisected.",
                      "Horizon: standard 34 arcminute refraction plus Sun/Moon apparent radius; no terrain or horizon dip.",
                      "Earth is the observing origin and intentionally omitted from the body list."],
            "bodies": results}
    # Preserve the old report key for the existing UTC workflow's default behavior.
    if timezone_name == "UTC":
        data["rise_set_utc_date"] = local_date.isoformat()
    return data


def render(data):
    rows = []
    for row in data["bodies"]:
        crossings = "<br>".join(html.escape(x["type"] + " " + x["local"])
                                for x in row["rise_set"]["events"])
        values = [row["body"].title(), row["ra_hours"], row["dec_deg"],
                  row["ecliptic_longitude_deg"], row["ecliptic_latitude_deg"],
                  row["distance_au"], row["altitude_deg"], row["azimuth_deg"]]
        rows.append("<tr>" + "".join("<td>" + html.escape(str(x)) + "</td>" for x in values)
                    + "<td>" + (crossings or html.escape(row["rise_set"]["state"])) + "</td></tr>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>Star Almanack Ephemera</title>"
            "<style>body{font:1rem/1.5 system-ui;background:#102039;color:white;margin:2rem}"
            "table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #9aa}"
            ".table-scroll{overflow-x:auto}</style>"
            "<h1>Observer Ephemera</h1><p>" + html.escape(data["instant_utc"]) + " · "
            + html.escape(str(data["observer"])) + "</p><p>Rise/set: "
            + html.escape(data["rise_set_local_date"] + " · " + data["timezone"])
            + "</p><div class='table-scroll'><table><tr><th>Body</th><th>RA (h)</th>"
            "<th>Dec (°)</th><th>Ecliptic λ (°)</th><th>Ecliptic β (°)</th>"
            "<th>Distance (AU)</th><th>Altitude (°)</th><th>Azimuth (°)</th>"
            "<th>Rise/set local time</th></tr>" + "".join(rows)
            + "</table></div><p>" + html.escape(data["precision"]) + "</p></html>")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instant", required=True, help="ISO 8601 instant, with Z or UTC offset")
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--elevation-m", default=0., type=float)
    parser.add_argument("--timezone", default="UTC", help="IANA timezone for rise/set civil date")
    parser.add_argument("--output", default="generated/ephemera", type=Path)
    args = parser.parse_args()
    dt = datetime.fromisoformat(args.instant.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        parser.error("UTC offset required in instant")
    data = calculate(dt, args.latitude, args.longitude, args.elevation_m, args.timezone)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ephemera.json").write_text(json.dumps(data, indent=2) + "\n")
    (args.output / "ephemera.html").write_text(render(data))
    print("Saved ephemera.json and ephemera.html", flush=True)


if __name__ == "__main__":
    main()
