#!/usr/bin/env python3
"""Independent geometric Besselian-style solar shadow elements.

No eclipse catalogs or third-party Besselian routines are used. Input positions
are barycentric Sun, Earth, Moon vectors in the same inertial frame and units
(km). Outputs use Earth's equatorial radius as the length unit.

The fundamental plane passes through Earth's center and is perpendicular to
the shadow axis (Sun -> Moon). Its basis is formed by projecting the inertial
north pole onto that plane, then taking east = north cross axis. The basis is
inertial, not an Earth-fixed longitude/latitude basis. For geographic contacts,
a separate Earth-orientation model is required.

This is a geometric implementation and has NOT yet been validated to production
eclipse timing accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

EARTH_EQUATORIAL_RADIUS_KM = 6378.137
SUN_RADIUS_KM = 695700.0
MOON_RADIUS_KM = 1737.4

Vector = tuple[float, float, float]


def add(a: Vector, b: Vector) -> Vector:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def subtract(a: Vector, b: Vector) -> Vector:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vector, factor: float) -> Vector:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def dot(a: Vector, b: Vector) -> float:
    return sum(u * v for u, v in zip(a, b))


def cross(a: Vector, b: Vector) -> Vector:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def norm(a: Vector) -> float:
    return sqrt(dot(a, a))


def unit(a: Vector) -> Vector:
    length = norm(a)
    if length == 0:
        raise ValueError("zero-length vector")
    return scale(a, 1.0 / length)


@dataclass(frozen=True)
class ShadowElements:
    x: float
    y: float
    gamma: float
    l1: float
    l2: float
    axis_distance_km: float
    sun_moon_distance_km: float
    fundamental_plane_offset_km: float


def solar_shadow_elements(
    sun_barycentric_km: Vector,
    earth_barycentric_km: Vector,
    moon_barycentric_km: Vector,
    *,
    north_pole: Vector = (0.0, 0.0, 1.0),
) -> ShadowElements:
    """Compute fundamental-plane axis intersection and signed cone radii.

    l1 is the penumbral radius and l2 is the signed umbral radius at the
    fundamental plane; l2 < 0 denotes antumbral geometry. The sign convention
    must be reconciled with production Besselian output before integration.
    """
    shadow_axis = unit(subtract(moon_barycentric_km, sun_barycentric_km))
    moon_from_earth = subtract(moon_barycentric_km, earth_barycentric_km)
    north = subtract(north_pole, scale(shadow_axis, dot(north_pole, shadow_axis)))
    if norm(north) < 1e-12:
        raise ValueError("shadow axis parallel to chosen north pole")
    north = unit(north)
    east = unit(cross(north, shadow_axis))
    # Shadow axis: Moon + s * shadow_axis. Solve projection onto plane.
    s = -dot(moon_from_earth, shadow_axis)
    intersection = add(moon_from_earth, scale(shadow_axis, s))
    x = dot(intersection, east) / EARTH_EQUATORIAL_RADIUS_KM
    y = dot(intersection, north) / EARTH_EQUATORIAL_RADIUS_KM
    separation = norm(subtract(moon_barycentric_km, sun_barycentric_km))
    # Signed distance from Moon toward Earth along the shadow direction.
    distance_from_moon = s
    penumbra_km = MOON_RADIUS_KM + distance_from_moon * (SUN_RADIUS_KM + MOON_RADIUS_KM) / separation
    umbra_km = MOON_RADIUS_KM - distance_from_moon * (SUN_RADIUS_KM - MOON_RADIUS_KM) / separation
    return ShadowElements(
        x=x, y=y, gamma=sqrt(x*x + y*y),
        l1=penumbra_km / EARTH_EQUATORIAL_RADIUS_KM,
        l2=umbra_km / EARTH_EQUATORIAL_RADIUS_KM,
        axis_distance_km=norm(intersection),
        sun_moon_distance_km=separation,
        fundamental_plane_offset_km=s,
    )
