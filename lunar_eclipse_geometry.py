"""Shared, frame-independent eclipse shadow geometry.

All vectors are geocentric Cartesian kilometres in the SAME inertial frame.
This module performs no ephemeris or UTC conversion. Its inputs must come
from a single authoritative position/time provider.

Solar geometry is handled separately; this module models Earth's shadow
at the Moon, including the finite apparent size of the Sun.
"""
from dataclasses import dataclass
from math import sqrt
from typing import Sequence

EARTH_RADIUS_KM = 6378.137
SUN_RADIUS_KM = 695700.0
MOON_RADIUS_KM = 1737.4


@dataclass(frozen=True)
class LunarShadow:
    axial_distance_km: float
    axis_offset_km: float
    umbra_radius_km: float
    penumbra_radius_km: float
    penumbral_margin_km: float
    umbral_margin_km: float
    totality_margin_km: float
    classification: str


def lunar_shadow_geometry(
    sun: Sequence[float],
    moon: Sequence[float],
    earth_radius_km: float = EARTH_RADIUS_KM,
    sun_radius_km: float = SUN_RADIUS_KM,
    moon_radius_km: float = MOON_RADIUS_KM,
) -> LunarShadow:
    """Compute the conical Earth-shadow intersection with the lunar sphere.

    A circular spherical-Earth model; atmospheric enlargement and oblateness
    are intentionally excluded until a documented physical model is selected.
    Contact times require a separate continuous root solver.
    """
    if not (earth_radius_km > 0 and sun_radius_km > earth_radius_km and moon_radius_km > 0):
        raise ValueError("invalid body radii")
    if len(sun) != 3 or len(moon) != 3:
        raise ValueError("expected 3-dimensional vectors")
    sun_dist = sqrt(sum(v*v for v in sun))
    if sun_dist <= sun_radius_km:
        raise ValueError("invalid Sun distance")
    direction = tuple(-v / sun_dist for v in sun)
    axial = sum(moon[i] * direction[i] for i in range(3))
    radial = sqrt(max(0.0, sum(v*v for v in moon) - axial*axial))
    umbra = earth_radius_km - axial * (sun_radius_km-earth_radius_km)/sun_dist
    penumbra = earth_radius_km + axial * (sun_radius_km+earth_radius_km)/sun_dist
    p_margin = penumbra + moon_radius_km - radial
    u_margin = umbra + moon_radius_km - radial
    t_margin = umbra - moon_radius_km - radial
    if axial <= 0 or p_margin < 0:
        kind = "none"
    elif umbra > moon_radius_km and t_margin >= 0:
        kind = "total"
    elif umbra > 0 and u_margin >= 0:
        kind = "partial"
    else:
        kind = "penumbral"
    return LunarShadow(axial, radial, umbra, penumbra, p_margin,
                       u_margin, t_margin, kind)
