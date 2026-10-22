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
