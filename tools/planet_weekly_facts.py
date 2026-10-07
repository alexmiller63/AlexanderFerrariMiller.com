"""Week-specific observing facts, joined by permanent Solar-System identity.

Positions, magnitude and rise/set come from the preserved page ephemeris.
Phase, motion and events use the same cached JPL calculation layer. No online
answer service or display-name identity matching is involved.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from html.parser import HTMLParser
import math

from star_almanack_ephemeris import StarAlmanackEphemeris
from skyfield.framelib import ecliptic_frame


class EphemerisParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.rows = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and 'ephemeris' in attrs.get('class', ''):
            self.rows = []
        if self.cell is not None and 'data-latin' in attrs:
            self.cell['attrs'].setdefault('data-latin', attrs['data-latin'])
        if self.rows is not None:
            if tag == 'tr':
                self.row = []
            elif tag in ('th', 'td') and self.row is not None:
                self.cell = {'attrs': attrs, 'text': ''}

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'] += data

    def handle_endtag(self, tag):
        if self.rows is None:
            return
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'table':
            self.tables.append(self.rows)
            self.rows = None


def preserved_facts(path):
    parser = EphemerisParser()
    parser.feed(path.read_text(encoding='utf-8'))
    result = {}
    for rows in parser.tables:
        if len(rows) < 5:
            continue
        for column, header in enumerate(rows[0][1:], 1):
            name = header['attrs'].get('data-latin', header['text']).strip().lower()
            observing = rows[2][column]['attrs']
            rise = rows[3][column]
            result[name] = {
                'observing': observing.get('data-normal-label', rows[2][column]['text']).strip(),
                'solar_glare': observing.get('data-solar-glare') == 'true',
                'ra_hours': float(rise['attrs']['data-ra-hours']),
                'dec_deg': float(rise['attrs']['data-dec-deg']),
                'sun_ra_hours': float(rise['attrs']['data-sun-ra-hours']),
                'rise': rise['text'].strip(), 'set': rows[4][column]['text'].strip(),
            }
    return result


def signed_angle(value):
    return (value + 180) % 360 - 180


def separation(a, b):
    ra1, ra2 = math.radians(a['ra_hours'] * 15), math.radians(b['ra_hours'] * 15)
    d1, d2 = math.radians(a['dec_deg']), math.radians(b['dec_deg'])
    return math.degrees(math.acos(max(-1, min(1, math.sin(d1)*math.sin(d2) + math.cos(d1)*math.cos(d2)*math.cos(ra1-ra2)))))


class WeekGeometry:
    def __init__(self, model):
        self.model = model

    @lru_cache(maxsize=None)
    def longitude(self, key, instant):
        t = self.model.ts.from_datetime(instant)
        apparent = self.model.earth.at(t).observe(self.model._body(key)).apparent()
        return float(apparent.frame_latlon(ecliptic_frame)[1].degrees)

    def velocity(self, key, instant):
        delta = timedelta(minutes=30)
        return signed_angle(self.longitude(key, instant+delta) - self.longitude(key, instant-delta)) * 24

    @staticmethod
    def crossings(function, start):
        """Bracket six-hour sign crossings, refine to a minute, exclude angle wraps."""
        found = []
        for step in range(28):
            left = start + timedelta(hours=6*step)
            right = left + timedelta(hours=6)
            fl, fr = function(left), function(right)
            if fl == 0 or (fl * fr < 0 and abs(fl-fr) < 180):
                for _ in range(10):
                    middle = left + (right-left)/2
                    fm = function(middle)
                    if fl*fm <= 0:
                        right = middle
                    else:
                        left, fl = middle, fm
                event = left + (right-left)/2
                if not found or event-found[-1] > timedelta(hours=1):
                    found.append(event)
        return found


def build_weekly_facts(year, week, page_path, routes, object_ids, model=None):
    model = model or StarAlmanackEphemeris()
    geometry = WeekGeometry(model)
    start = datetime.combine(date.fromisocalendar(year, week, 1), datetime.min.time(), timezone.utc)
    preserved = preserved_facts(page_path)
    output = {}
    for route in routes:
        name = route['planet']
        key = name.lower()
        facts = dict(preserved[key])
        facts.update(object_id=object_ids[name], name=name, snapshot_utc=start.isoformat(),
                     guide_star=route['star'], guide_star_fixed_object_id=route['star_fixed_object_id'],
                     guide_separation_deg=route['sky_separation_deg'], events=[], close_pairs=[])
        if key not in model.bodies:
            raise RuntimeError(f'Missing calculation kernel for {name}; prepare ephemeris kernels before generating Sky Notes')
        t = model.ts.from_datetime(start)
        apparent = model.earth.at(t).observe(model._body(key)).apparent()
        facts['magnitude'] = model.sample(key, start.date()).magnitude
        facts['illuminated_percent'] = round(float(apparent.fraction_illuminated(model.sun)) * 100, 1)
        facts['elongation_deg'] = round(separation(facts, preserved['sun']), 1)
        signed_elongation = signed_angle(geometry.longitude(key, start)-geometry.longitude('sun', start))
        facts['solar_side'] = 'east' if signed_elongation >= 0 else 'west'
        if key == 'moon':
            facts['phase_trend'] = 'waxing' if signed_elongation >= 0 else 'waning'
        velocity = geometry.velocity(key, start)
        facts['motion_deg_per_day'] = round(velocity, 4)
        facts['motion'] = 'retrograde' if velocity < 0 else 'direct'
        for instant in geometry.crossings(lambda x: geometry.velocity(key, x), start):
            after = geometry.velocity(key, instant+timedelta(hours=1))
            facts['events'].append(f"Station {instant:%b %d %H:%M} UTC: turns {'retrograde' if after < 0 else 'direct'}.")
        for alignment, angle in [('solar conjunction', 0), ('opposition', 180)]:
            if alignment == 'opposition' and key in ('mercury', 'venus'):
                continue
            for instant in geometry.crossings(lambda x: signed_angle(geometry.longitude(key, x)-geometry.longitude('sun', x)-angle), start):
                facts['events'].append(f"{alignment.capitalize()} in ecliptic longitude {instant:%b %d %H:%M} UTC.")
        altitude = math.degrees(math.asin(math.sin(math.radians(45))*math.sin(math.radians(facts['dec_deg'])) + math.cos(math.radians(45))*math.cos(math.radians(facts['dec_deg']))*math.cos(math.radians(15*(facts['sun_ra_hours']+9-facts['ra_hours'])))))
        facts['altitude_21_last_45n_deg'] = round(altitude, 1)
        facts['source'] = 'Preserved weekly ephemeris; cached JPL/NAIF kernels through StarAlmanackEphemeris'
        output[facts['object_id']] = facts
    bodies = list(output.values())
    for index, first in enumerate(bodies):
        for second in bodies[index+1:]:
            distance = separation(first, second)
            if distance <= 5:
                for a, b in [(first, second), (second, first)]:
                    a['close_pairs'].append({'object_id': b['object_id'], 'name': b['name'], 'separation_deg': round(distance, 1)})
            for instant in geometry.crossings(lambda x: signed_angle(geometry.longitude(first['name'].lower(), x)-geometry.longitude(second['name'].lower(), x)), start):
                for a, b in [(first, second), (second, first)]:
                    a['events'].append(f"Conjunction with {b['name']} in ecliptic longitude {instant:%b %d %H:%M} UTC.")
    for facts in bodies:
        facts['dek'], facts['body'] = fact_prose(facts)
    return output


def fact_prose(facts):
    name = facts['name']
    visibility = 'In solar glare' if facts['solar_glare'] else facts['observing']
    brightness = f"; magnitude {facts['magnitude']:.1f}" if facts['magnitude'] is not None else ''
    dek = f"{visibility}{brightness}; {facts['motion']} motion; {facts['illuminated_percent']:.1f}% illuminated."
    if not facts['solar_glare'] and facts['altitude_21_last_45n_deg'] < 0:
        dek += ' Below the horizon at 21:00 local apparent solar time, 45°N.'
    dek += ' Monday 00:00 UTC snapshot.'
    if facts['events']:
        dek += ' ' + ' '.join(facts['events'])
    sentences = [f"{name}: {visibility.lower()} at the Monday 00:00 UTC snapshot."]
    if not facts['solar_glare']:
        alt = facts['altitude_21_last_45n_deg']
        sentences.append(f"At 45°N and 21:00 local apparent solar time, it is {abs(alt):.1f}° {'above' if alt >= 0 else 'below'} the horizon.")
    sentences.append(f"Rises {facts['rise']}; sets {facts['set']} (45°N, local apparent solar time).")
    if facts['magnitude'] is not None:
        sentences.append(f"Visual magnitude {facts['magnitude']:.1f}.")
    trend = facts.get('phase_trend', '')
    illumination = facts['illuminated_percent']
    phase = 'crescent' if illumination < 49 else 'half-lit' if illumination <= 51 else 'gibbous' if illumination < 99 else 'nearly full'
    sentences.append(f"The disk is {illumination:.1f}% illuminated ({(trend+' ') if trend else ''}{phase}).")
    sentences.append(f"It is {facts['elongation_deg']:.1f}° from the Sun, on its {facts['solar_side']} side.")
    sentences.append(f"Motion is {facts['motion']} at {abs(facts['motion_deg_per_day']):.3f}° per day in ecliptic longitude at the snapshot.")
    sentences.append(f"Position reference: {facts['guide_star']}, {facts['guide_separation_deg']:.1f}° away.")
    for pair in facts['close_pairs']:
        sentences.append(f"{pair['name']} is {pair['separation_deg']:.1f}° away at the snapshot.")
    sentences.extend(facts['events'])
    return dek, ' '.join(sentences)
