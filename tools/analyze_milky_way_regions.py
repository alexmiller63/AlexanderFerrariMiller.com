#!/usr/bin/env python3
"""Sample Mellinger optical data for candidate named Milky Way regions.

This is an analysis tool, not a second Milky Way boundary model. Vieira ``ol1``
remains authoritative for ``milky_way.inside``. Mellinger data are used only to
measure internal optical prominence/contrast so named regions can later be
validated and derived without changing the existing outer boundary.

SkyView supplies the Mellinger survey as three calibrated optical channels.
The script requests small linear-scaled FITS cutouts around validation anchors,
computes a robust center-versus-surround contrast for each channel, and writes
machine-readable JSON. No visibility threshold is hard-coded here: the purpose
of the measurements is to let the validation suite determine that threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".cache" / "source-data" / "milky-way-mellinger-validation.json"
SKYVIEW = "https://skyview.gsfc.nasa.gov/cgi-bin/images"
SURVEYS = ("mell-r", "mell-g", "mell-b")

# Independent bright-region anchors published by the Astronomical Society of
# Southern Africa. These are validation anchors, not hand-drawn region borders.
BRIGHT_ANCHORS = (
    {"name": "Carina", "ra_h": 10.75, "dec_deg": -60.0, "expected": "bright"},
    {"name": "Norma", "ra_h": 16.30, "dec_deg": -53.0, "expected": "bright"},
    {"name": "Sagittarius", "ra_h": 18.00, "dec_deg": -29.0, "expected": "bright"},
    {"name": "Scutum", "ra_h": 18.75, "dec_deg": -7.0, "expected": "bright"},
    {"name": "Cygnus", "ra_h": 19.50, "dec_deg": 30.0, "expected": "bright"},
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--size", type=float, default=12.0, help="cutout width in degrees")
    p.add_argument("--pixels", type=int, default=121, help="square cutout pixels")
    p.add_argument("--offline", action="store_true", help="read an existing output only")
    return p.parse_args()


def fits_values(payload: bytes) -> tuple[int, int, list[float]]:
    """Read a simple 2-D primary FITS image without adding a runtime dependency."""
    cards: list[str] = []
    end = None
    for offset in range(0, len(payload), 80):
        card = payload[offset : offset + 80].decode("ascii", errors="replace")
        cards.append(card)
        if card.startswith("END"):
            end = offset + 80
            break
    if end is None:
        raise ValueError("FITS END card not found")

    header: dict[str, str] = {}
    for card in cards:
        if len(card) >= 10 and card[8:10] == "= ":
            header[card[:8].strip()] = card[10:80].split("/", 1)[0].strip()

    bitpix = int(header["BITPIX"])
    nx, ny = int(header["NAXIS1"]), int(header["NAXIS2"])
    bscale = float(header.get("BSCALE", "1"))
    bzero = float(header.get("BZERO", "0"))
    data_start = ((end + 2879) // 2880) * 2880
    count = nx * ny

    import struct

    formats = {8: ">B", 16: ">h", 32: ">i", -32: ">f", -64: ">d"}
    if bitpix not in formats:
        raise ValueError(f"Unsupported BITPIX={bitpix}")
    fmt = formats[bitpix]
    step = abs(bitpix) // 8
    values = [
        struct.unpack(fmt, payload[data_start + i * step : data_start + (i + 1) * step])[0]
        * bscale
        + bzero
        for i in range(count)
    ]
    return nx, ny, values


def request_channel(anchor: dict[str, Any], survey: str, size: float, pixels: int) -> tuple[int, int, list[float]]:
    params = {
        "Survey": survey,
        "Position": f"{anchor['ra_h'] * 15.0},{anchor['dec_deg']}",
        "Coordinates": "J2000",
        "Projection": "Tan",
        "Size": str(size),
        "Pixels": f"{pixels},{pixels}",
        "Scaling": "Linear",
        "Return": "FITS",
    }
    url = SKYVIEW + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as response:
        return fits_values(response.read())


def robust_contrast(nx: int, ny: int, values: list[float]) -> dict[str, float]:
    """Compare a central disk with an outer annulus using medians.

    Radius is normalized to half the image width. Center r<=0.25 samples the
    named anchor; surround 0.55<=r<=0.90 estimates its local sky environment.
    """
    cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
    scale = min(nx, ny) / 2.0
    center: list[float] = []
    surround: list[float] = []
    for y in range(ny):
        for x in range(nx):
            value = values[y * nx + x]
            if not math.isfinite(value):
                continue
            r = math.hypot(x - cx, y - cy) / scale
            if r <= 0.25:
                center.append(value)
            elif 0.55 <= r <= 0.90:
                surround.append(value)
    if not center or not surround:
        raise ValueError("insufficient finite FITS pixels for contrast measurement")
    c = statistics.median(center)
    b = statistics.median(surround)
    return {
        "center_median": c,
        "surround_median": b,
        "contrast": (c - b) / b if b else float("nan"),
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "validation measurements for named Milky Way regions",
        "boundary_model": "Vieira ol1 remains authoritative; this file does not redefine it",
        "source": "Axel Mellinger optical survey via NASA SkyView",
        "threshold": None,
        "anchors": [],
    }
    for anchor in BRIGHT_ANCHORS:
        entry = dict(anchor)
        entry["channels"] = {}
        contrasts: list[float] = []
        for survey in SURVEYS:
            nx, ny, values = request_channel(anchor, survey, args.size, args.pixels)
            measurement = robust_contrast(nx, ny, values)
            entry["channels"][survey] = measurement
            if math.isfinite(measurement["contrast"]):
                contrasts.append(measurement["contrast"])
        entry["mean_rgb_contrast"] = statistics.mean(contrasts) if contrasts else None
        result["anchors"].append(entry)
        print(f"{entry['name']}: mean RGB contrast={entry['mean_rgb_contrast']:.6f}")
    return result


def main() -> int:
    args = parse_args()
    if args.offline:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        for entry in data.get("anchors", []):
            print(f"{entry['name']}: mean RGB contrast={entry.get('mean_rgb_contrast')}")
        return 0

    result = analyze(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
