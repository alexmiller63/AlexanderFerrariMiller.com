#!/usr/bin/env python3
"""
Normalize the 36 fixed-format CDS ELP2000-82B coefficient files.

The original CDS VI/79 files are archival model data and must remain unaltered.
This program reads them using the exact fixed-width FORMAT statements in the
reference Bureau des Longitudes Fortran program `elp82b.f`, then writes a
machine-readable JSON representation plus provenance hashes.

Reference Fortran formats
-------------------------
ELP1-ELP3:
    1001 format (4i3,2x,f13.5,6(2x,f10.2))

ELP4-ELP9 and ELP22-ELP36:
    1002 format (5i3,1x,f9.5,1x,f9.5,1x,f9.3)

ELP10-ELP21:
    1003 format (11i3,1x,f9.5,1x,f9.5,1x,f9.3)

Each source file begins with one 50-character descriptive header record.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _int_field(line: str, start: int, width: int = 3) -> int:
    text = line[start:start + width]
    if len(text) != width:
        raise ValueError(f"short integer field at columns {start + 1}-{start + width}")
    return int(text)


def _float_field(line: str, start: int, width: int) -> float:
    text = line[start:start + width]
    if len(text) != width:
        raise ValueError(f"short float field at columns {start + 1}-{start + width}")
    # Accept Fortran D exponents as well as ordinary decimal notation.
    return float(text.replace("D", "E").replace("d", "e"))


def parse_main_problem(line: str) -> dict[str, Any]:
    """Parse FORMAT 1001: 4i3,2x,f13.5,6(2x,f10.2)."""
    ilu = [_int_field(line, 3 * i) for i in range(4)]

    pos = 14  # 4*I3 + 2X
    coef = [_float_field(line, pos, 13)]
    pos += 13

    for _ in range(6):
        pos += 2
        coef.append(_float_field(line, pos, 10))
        pos += 10

    return {"ilu": ilu, "coef": coef}


def parse_figure_tide(line: str) -> dict[str, Any]:
    """Parse FORMAT 1002: 5i3,1x,f9.5,1x,f9.5,1x,f9.3."""
    values = [_int_field(line, 3 * i) for i in range(5)]
    iz = values[0]
    ilu = values[1:5]

    pos = 16  # 5*I3 + 1X
    pha = _float_field(line, pos, 9)
    pos += 10  # F9.5 + 1X
    x = _float_field(line, pos, 9)
    pos += 10  # F9.5 + 1X
    per = _float_field(line, pos, 9)

    return {"iz": iz, "ilu": ilu, "pha": pha, "x": x, "per": per}


def parse_planetary(line: str) -> dict[str, Any]:
    """Parse FORMAT 1003: 11i3,1x,f9.5,1x,f9.5,1x,f9.3."""
    ipla = [_int_field(line, 3 * i) for i in range(11)]

    pos = 34  # 11*I3 + 1X
    pha = _float_field(line, pos, 9)
    pos += 10  # F9.5 + 1X
    x = _float_field(line, pos, 9)
    pos += 10  # F9.5 + 1X
    per = _float_field(line, pos, 9)

    return {"ipla": ipla, "pha": pha, "x": x, "per": per}


def family_for(file_number: int) -> str:
    if 1 <= file_number <= 3:
        return "main_problem"
    if 4 <= file_number <= 9 or 22 <= file_number <= 36:
        return "figure_tide_relativity_solar_eccentricity"
    if 10 <= file_number <= 21:
        return "planetary_perturbations"
    raise ValueError(f"invalid ELP file number: {file_number}")


def parse_record(file_number: int, line: str) -> dict[str, Any]:
    family = family_for(file_number)
    if family == "main_problem":
        return parse_main_problem(line)
    if family == "planetary_perturbations":
        return parse_planetary(line)
    return parse_figure_tide(line)


def parse_elp_file(path: Path, file_number: int) -> dict[str, Any]:
    with path.open("r", encoding="ascii", errors="strict") as f:
        header_line = f.readline()
        if header_line == "":
            raise ValueError(f"{path}: empty file")

        header = header_line.rstrip("\r\n")
        records = []

        for line_number, raw in enumerate(f, start=2):
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            try:
                records.append(parse_record(file_number, line))
            except Exception as exc:
                raise ValueError(
                    f"{path.name}:{line_number}: cannot parse fixed-format record: "
                    f"{exc}; record={line!r}"
                ) from exc

    return {
        "name": path.name,
        "family": family_for(file_number),
        "header": header,
        "record_count": len(records),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "records": records,
    }


def normalize(source_directory: Path, output: Path) -> None:
    tables = []

    for i in range(1, 37):
        path = source_directory / f"ELP{i}"
        if not path.exists():
            raise SystemExit(f"missing {path}")
        tables.append(parse_elp_file(path, i))

    provenance = []
    for name in ("ReadMe", "elp82b.f", "example.f", "elp82b.ps"):
        path = source_directory / name
        if path.exists():
            provenance.append({
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

    payload = {
        "model": "ELP2000-82B",
        "source_catalog": "CDS/VizieR VI/79",
        "parser_authority": "elp82b.f",
        "formats": {
            "ELP1-ELP3": "4i3,2x,f13.5,6(2x,f10.2)",
            "ELP4-ELP9_ELP22-ELP36": "5i3,1x,f9.5,1x,f9.5,1x,f9.3",
            "ELP10-ELP21": "11i3,1x,f9.5,1x,f9.5,1x,f9.3",
        },
        "provenance": provenance,
        "tables": tables,
    }

    output.write_text(
        json.dumps(payload, indent=2, separators=(",", ": ")) + "\n",
        encoding="utf-8",
    )

    total_records = sum(table["record_count"] for table in tables)
    print(f"wrote {output}")
    print(f"parsed 36 tables, {total_records} coefficient records")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Normalize the 36 CDS ELP2000-82B fixed-format tables."
    )
    ap.add_argument("source_directory", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    normalize(args.source_directory, args.output)


if __name__ == "__main__":
    main()
