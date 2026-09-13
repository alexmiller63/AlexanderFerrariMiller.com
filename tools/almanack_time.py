#!/usr/bin/env python3
"""Canonical time handling for Star Almanack astronomy.

Astronomical event solvers should carry event instants as JDTDB (Julian Date,
Barycentric Dynamical Time). Civil UTC exists only at the publication boundary.

Horizons OBSERVER tables are UT/UTC (after 1962), not TDB. When requesting
observer quantities, also request quantity 30 (TDB-UT). Convert each Horizons
JD(UTC) sample to JDTDB with::

    jd_tdb = jd_utc + (tdb_minus_utc_seconds / 86400)

The conversion offset is carried with an instant so the final publication UTC
can be recovered without treating an unlabeled Julian Date as interchangeable
between time scales.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

SECONDS_PER_DAY = 86400.0
UNIX_EPOCH_JD_UTC = 2440587.5


def jd_utc_to_datetime(jd_utc: float) -> datetime:
    """Convert JD(UTC) to a timezone-aware UTC datetime."""
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=jd_utc - UNIX_EPOCH_JD_UTC
    )


def datetime_to_jd_utc(ts: datetime) -> float:
    """Convert a datetime to JD(UTC). Naive datetimes are rejected."""
    if ts.tzinfo is None:
        raise ValueError("UTC conversion requires a timezone-aware datetime")
    utc = ts.astimezone(timezone.utc)
    return UNIX_EPOCH_JD_UTC + (
        utc - datetime(1970, 1, 1, tzinfo=timezone.utc)
    ).total_seconds() / SECONDS_PER_DAY


def jd_utc_to_jd_tdb(jd_utc: float, tdb_minus_utc_seconds: float) -> float:
    """Convert JD(UTC) to JDTDB using the Horizons TDB-UT quantity."""
    return jd_utc + tdb_minus_utc_seconds / SECONDS_PER_DAY


def jd_tdb_to_jd_utc(jd_tdb: float, tdb_minus_utc_seconds: float) -> float:
    """Convert JDTDB to JD(UTC) using the corresponding TDB-UT quantity."""
    return jd_tdb - tdb_minus_utc_seconds / SECONDS_PER_DAY


@dataclass(frozen=True, order=True)
class AstroInstant:
    """One astronomical instant represented canonically as JDTDB.

    ``tdb_minus_utc_seconds`` is retained solely to provide the civil UTC
    publication representation. Astronomical comparisons and interpolation
    should use ``jd_tdb``.
    """

    jd_tdb: float
    tdb_minus_utc_seconds: float

    @classmethod
    def from_horizons_utc(
        cls, jd_utc: float, tdb_minus_utc_seconds: float
    ) -> "AstroInstant":
        return cls(
            jd_tdb=jd_utc_to_jd_tdb(jd_utc, tdb_minus_utc_seconds),
            tdb_minus_utc_seconds=tdb_minus_utc_seconds,
        )

    @property
    def jd_utc(self) -> float:
        return jd_tdb_to_jd_utc(self.jd_tdb, self.tdb_minus_utc_seconds)

    def utc_datetime(self) -> datetime:
        return jd_utc_to_datetime(self.jd_utc)

    def publication_utc(self, quantum_seconds: int = 1) -> datetime:
        """Return one rounded UTC datetime for both published date and time.

        The date and clock string must always be derived from this same object.
        That prevents a rounded clock time from crossing midnight while the
        event remains attached to the previous UTC date.
        """
        if quantum_seconds <= 0:
            raise ValueError("quantum_seconds must be positive")
        ts = self.utc_datetime()
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        seconds = (ts - epoch).total_seconds()
        rounded = int(seconds / quantum_seconds + 0.5) * quantum_seconds
        return epoch + timedelta(seconds=rounded)

    def publication_date(self, quantum_seconds: int = 1) -> date:
        return self.publication_utc(quantum_seconds).date()

    def publication_time_text(self, quantum_seconds: int = 1) -> str:
        return self.publication_utc(quantum_seconds).strftime("%H:%M:%S UTC")


def interpolate_instant(
    a: AstroInstant,
    b: AstroInstant,
    fraction: float,
) -> AstroInstant:
    """Linearly interpolate an instant in JDTDB and its UTC conversion offset."""
    f = min(1.0, max(0.0, fraction))
    return AstroInstant(
        jd_tdb=a.jd_tdb + (b.jd_tdb - a.jd_tdb) * f,
        tdb_minus_utc_seconds=(
            a.tdb_minus_utc_seconds
            + (b.tdb_minus_utc_seconds - a.tdb_minus_utc_seconds) * f
        ),
    )
