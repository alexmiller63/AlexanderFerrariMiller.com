"""Independent geocentric lunar-eclipse shadow geometry.

Uses the same J2000 Sun/Moon vectors and UTC->TT approximation as the
existing solar engine. No eclipse catalog or external service is consulted.
All linear dimensions are kilometres.
"""
from dataclasses import dataclass
import math

from eclipse_engine import (
    EARTH_RADIUS_KM, MOON_RADIUS_KM, SUN_RADIUS_KM,
    EclipseEngine, utc_to_tdb_approx, sun_vector_j2000,
)

@dataclass(frozen=True)
class LunarShadow:
    jd_utc: float
    axis_distance_km: float
    moon_distance_km: float
    umbra_radius_km: float
    penumbra_radius_km: float
    penumbral_margin_km: float
    umbral_margin_km: float
    totality_margin_km: float
    eclipse_type: str

def lunar_shadow_at_utc_jd(engine: EclipseEngine, jd_utc: float) -> LunarShadow:
    jd = utc_to_tdb_approx(jd_utc)
    moon = engine.moon_vector_j2000(jd)
    sun = sun_vector_j2000(jd)
    sun_distance = sun.norm()
    moon_distance = moon.norm()
    # Earth shadow axis extends in the direction opposite the Sun.
    axis = sun.unit() * -1.0
    axial_distance = moon.dot(axis)
    transverse = (moon - axis * axial_distance).norm()
    if axial_distance <= 0:
        return LunarShadow(jd_utc, transverse, moon_distance, 0., 0.,
                           float('inf'), float('inf'), float('inf'), 'none')
    # Similar triangles for the umbral and penumbral cones at the
    # Moon's projected distance behind Earth.
    umbra = EARTH_RADIUS_KM - axial_distance * (SUN_RADIUS_KM - EARTH_RADIUS_KM) / sun_distance
    penumbra = EARTH_RADIUS_KM + axial_distance * (SUN_RADIUS_KM + EARTH_RADIUS_KM) / sun_distance
    p_margin = transverse - (penumbra + MOON_RADIUS_KM)
    u_margin = transverse - (umbra + MOON_RADIUS_KM)
    t_margin = transverse + MOON_RADIUS_KM - umbra
    kind = ('none' if p_margin > 0 else
            'penumbral' if u_margin > 0 else
            'partial' if t_margin > 0 else 'total')
    return LunarShadow(jd_utc, transverse, moon_distance, umbra, penumbra,
                       p_margin, u_margin, t_margin, kind)

def _minimize(f, a, b, iterations=55):
    """Golden-section minimum over a bounded Julian-date interval."""
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    x, y = b - phi * (b-a), a + phi * (b-a)
    fx, fy = f(x), f(y)
    for _ in range(iterations):
        if fx <= fy:
            b, y, fy = y, x, fx
            x = b - phi * (b-a)
            fx = f(x)
        else:
            a, x, fx = x, y, fy
            y = a + phi * (b-a)
            fy = f(y)
    return (a+b)/2.0

def _bisect(f, a, b, iterations=45):
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        raise ValueError("contact root is not bracketed")
    for _ in range(iterations):
        mid = (a+b)/2.0
        fm = f(mid)
        if fa * fm <= 0:
            b, fb = mid, fm
        else:
            a, fa = mid, fm
    return (a+b)/2.0

def find_lunar_eclipse(engine: EclipseEngine, jd_center: float,
                       search_hours: float = 18.0):
    """Find closest shadow alignment and all applicable contacts.

    jd_center should be within roughly 18 hours of full Moon. Return None
    if the lunar disc does not enter Earth's penumbra.
    """
    half = search_hours / 24.0
    step = 0.5 / 24.0
    samples = [jd_center-half+i*step
               for i in range(int(2*half/step)+1)]
    best = min(samples, key=lambda t: lunar_shadow_at_utc_jd(
        engine, t).axis_distance_km)
    peak = _minimize(lambda t: lunar_shadow_at_utc_jd(
        engine, t).axis_distance_km, best-step, best+step)
    geom = lunar_shadow_at_utc_jd(engine, peak)
    if geom.eclipse_type == 'none':
        return None
    contacts = {}
    for name, field in (('P', 'penumbral_margin_km'),
                        ('U', 'umbral_margin_km'),
                        ('T', 'totality_margin_km')):
        f = lambda t, field=field: getattr(
            lunar_shadow_at_utc_jd(engine, t), field)
        if f(peak) > 0:
            continue
        for side, label in ((-1, name+'1'), (1, name+'4' if name == 'T' else name+'2')):
            prev = peak
            # Contact times can lie several hours from maximum.
            for i in range(1, 49):
                t = peak + side*i*(0.25/24.0)
                if f(prev)*f(t) <= 0:
                    contacts[label] = _bisect(f, min(prev,t), max(prev,t))
                    break
                prev = t
            else:
                raise RuntimeError('Could not bracket lunar contact '+label)
    # Standard chronological naming: P1 P4, U1 U4, U2 U3.
    renamed = {}
    for key, value in contacts.items():
        renamed[{'P2':'P4','U2':'U4','T1':'U2','T4':'U3'}.get(key,key)] = value
    return {'greatest_jd_utc': peak, 'type': geom.eclipse_type,
            'geometry': geom, 'contacts_jd_utc': renamed}
