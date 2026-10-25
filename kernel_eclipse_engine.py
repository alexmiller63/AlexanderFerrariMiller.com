"""Eclipse geometry using locally cached JPL positions in the J2000 frame."""
from pathlib import Path

from skyfield.api import load, load_file
from skyfield.framelib import ecliptic_J2000_frame

from eclipse_engine import EclipseEngine, Vec3


class KernelEclipseEngine(EclipseEngine):
    """Retain the project's shadow geometry, replacing the compact positions."""

    def __init__(self, kernel_path):
        path = Path(kernel_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.kernel = load_file(str(path))
        self.timescale = load.timescale(builtin=True)

    def _vector(self, body, jd_tdb):
        time = self.timescale.tdb_jd(jd_tdb)
        xyz = (self.kernel[body] - self.kernel['earth']).at(time).frame_xyz(ecliptic_J2000_frame).km
        return Vec3(*(float(value) for value in xyz))

    def moon_vector_j2000(self, jd_tdb):
        return self._vector('moon', jd_tdb)

    def sun_vector_j2000(self, jd_tdb):
        return self._vector('sun', jd_tdb)
