#!/usr/bin/env python3
"""Acquire Nancy Roman's CDS VI/42 constellation-membership lookup once.

VI/42 is the authoritative machine-readable lookup for determining which
constellation contains a position.  The downloaded snapshot is repository
owned after acquisition and is reused by subsequent builds.
"""
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "reference-data" / "roman-vi42" / "data.dat"
URL = "https://cdsarc.cds.unistra.fr/ftp/VI/42/data.dat"


def validate(text: str) -> None:
    rows = [line for line in text.splitlines() if line.strip()]
    if len(rows) != 357:
        raise SystemExit(f"expected 357 VI/42 rows, found {len(rows)}")
    for number, line in enumerate(rows, 1):
        try:
            float(line[1:8])
            float(line[9:16])
            float(line[17:25])
            abbreviation = line[26:29].strip()
        except (ValueError, IndexError) as exc:
            raise SystemExit(f"invalid VI/42 row {number}: {line!r}") from exc
        if len(abbreviation) != 3:
            raise SystemExit(f"invalid VI/42 constellation at row {number}: {line!r}")


def main() -> None:
    if DEST.exists():
        validate(DEST.read_text(encoding="ascii"))
        print(f"Reusing cached Roman VI/42 snapshot: {DEST.relative_to(ROOT)}")
        return

    request = Request(URL, headers={"User-Agent": "Star-Almanack-reference-data/1.0"})
    with urlopen(request, timeout=60) as response:
        text = response.read().decode("ascii")
    validate(text)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(text if text.endswith("\n") else text + "\n", encoding="ascii")
    print(f"Acquired Roman VI/42 snapshot: {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
