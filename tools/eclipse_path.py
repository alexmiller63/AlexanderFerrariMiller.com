"""Star Almanack central solar-shadow tracks from Sun/Moon vectors.

Uses the same instantaneous geometric cones and spherical Earth as the
catalog's hybrid classifier. Skyfield supplies frame/time rotations only;
no published eclipse paths, maps, coordinates, or Besselian elements are read.
A central-axis track is not a path boundary or a partial-visibility footprint.
"""
import math
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eclipse_engine import EARTH_RADIUS_KM, MOON_RADIUS_KM, SUN_RADIUS_KM, jd_to_iso_utc


def axis_surface_point(moon, sun):
    """Nearest forward intersection of the shadow axis with spherical Earth."""
    direction = (moon - sun).unit()
    distance = -moon.dot(direction)
    if distance <= 0:
        return None
    closest = moon + direction * distance
    discriminant = EARTH_RADIUS_KM**2 - closest.dot(closest)
    if discriminant < 0:
        return None
    along = distance - math.sqrt(discriminant)
    if along < 0:
        return None
    return moon + direction * along


def split_track(points):
    """Split map polylines at longitude wraps and changes of central phase."""
    segments = []
    for point in points:
        if not segments or abs(point['longitude_deg'] - segments[-1][-1]['longitude_deg']) > 180:
            segments.append([point])
        elif point['phase'] != segments[-1][-1]['phase']:
            # Share the join so the displayed sampled line has no gap.
            segments.append([segments[-1][-1], point])
        else:
            segments[-1].append(point)
    return segments


def central_path(engine, event, step_seconds=60):
    """Return a sampled central track, with geocentric latitude/east longitude.

    The two rounded axis-limit instants can fall just outside the surface;
    skip those rather than projecting an imaginary intersection onto Earth.
    UT1 and polar-motion behavior is Skyfield's locally loaded timescale;
    future UT1 is an estimate, and no IERS data is downloaded here.
    """
    if not math.isfinite(step_seconds) or step_seconds < 1:
        raise ValueError('Path sample interval must be finite and at least one second')
    result = {
        'model': 'Spherical Earth; instantaneous geometric shadow axis',
        'earth_radius_km': EARTH_RADIUS_KM,
        'latitude_convention': 'Geocentric latitude; longitude positive east',
        'rotation_source': 'Skyfield ITRS rotation; built-in timescale UT1 estimate; no downloaded Earth-orientation data',
        'step_seconds': step_seconds,
        'points': [],
    }
    if event['type'] == 'partial':
        return result
    contacts = event.get('contacts_utc', {})
    if isinstance(contacts, str):
        import json
        contacts = json.loads(contacts)
    if not contacts.get('axis_entry') or not contacts.get('axis_exit'):
        raise ValueError('Central event is missing its axis entry/exit times')
    # Lazy astronomy imports leave pure intersection tests dependency-free.
    from skyfield.api import load
    from skyfield.framelib import ecliptic_J2000_frame, itrs
    import numpy as np
    ts = getattr(engine, 'timescale', None) or load.timescale(builtin=True)

    def instant(value):
        return ts.from_datetime(datetime.fromisoformat(value.replace('Z', '+00:00')))

    start = instant(contacts['axis_entry'])
    end = instant(contacts['axis_exit'])
    greatest = instant(event['greatest_utc'])
    seconds = (float(end.tt) - float(start.tt)) * 86400.0
    if seconds <= 0:
        raise ValueError('Axis exit must follow axis entry')
    offsets = {i * step_seconds for i in range(math.floor(seconds / step_seconds) + 1)}
    offsets.add(seconds)
    offsets.add((float(greatest.tt) - float(start.tt)) * 86400.0)
    for offset in sorted(offsets):
        if offset < 0 or offset > seconds:
            continue
        t = ts.tt_jd(float(start.tt) + offset / 86400.0)
        # Preserve the existing catalog engine's time/geometry convention.
        utc = t.utc_datetime()
        from eclipse_engine import gregorian_to_jd
        jd = gregorian_to_jd(utc.year, utc.month, utc.day,
                             utc.hour + utc.minute / 60 + (utc.second + utc.microsecond / 1e6) / 3600)
        g = engine.geometry_at_utc_jd(jd)
        point = axis_surface_point(g.moon, g.sun)
        if point is None:
            continue
        # Engine vectors are ecliptic J2000; rotate to ICRF then Earth-fixed.
        icrf = ecliptic_J2000_frame.rotation_at(t).T @ np.array([point.x, point.y, point.z])
        fixed = itrs.rotation_at(t) @ icrf
        latitude = math.degrees(math.atan2(fixed[2], math.hypot(fixed[0], fixed[1])))
        longitude = math.degrees(math.atan2(fixed[1], fixed[0]))
        along = (point - g.moon).norm()
        core = MOON_RADIUS_KM - along * (SUN_RADIUS_KM - MOON_RADIUS_KM) / g.sun_moon_distance_km
        result['points'].append({
            'utc': jd_to_iso_utc(jd),
            'latitude_deg': round(latitude, 6),
            'longitude_deg': round(longitude, 6),
            'phase': 'total' if core > 0 else 'annular' if core < 0 else 'transition',
            'signed_core_radius_km': round(core, 6),
        })
    if len(result['points']) < 2:
        raise ValueError('Central eclipse produced fewer than two surface points')
    # Whole-second publication can make a boundary/greatest sample coincide.
    result['points'] = list({p['utc']: p for p in result['points']}.values())
    return result


def path_geojson(event):
    """GeoJSON line features, split at the dateline and phase joins."""
    path = event['central_path']
    features = []
    for segment in split_track(path['points']):
        if len(segment) < 2:
            continue
        features.append({'type': 'Feature', 'properties': {
            'eclipse_id': event['id'], 'phase': segment[-1]['phase'],
            'begin_utc': segment[0]['utc'], 'end_utc': segment[-1]['utc'],
            'model': path['model'], 'latitude_convention': path['latitude_convention'],
        }, 'geometry': {'type': 'LineString', 'coordinates': [
            [p['longitude_deg'], p['latitude_deg']] for p in segment]}})
    return {'type': 'FeatureCollection', 'features': features,
            'properties': {k: v for k, v in path.items() if k != 'points'}}
