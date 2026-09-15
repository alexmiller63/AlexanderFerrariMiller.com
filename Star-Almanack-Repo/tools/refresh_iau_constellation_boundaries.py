#!/usr/bin/env python3
"""Explicitly refresh the repository-owned IAU J2000 constellation-boundary snapshot.

This is a maintenance tool, not part of normal Almanack generation. Normal builds
must consume the committed snapshot and must never fetch these files live.
"""
from __future__ import annotations

import pathlib
import urllib.request

BASE = "https://iauarchive.eso.org/static/public/constellations/txt"
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "reference-data" / "iau-constellation-boundaries"

ABBR = "and ant aps aqr aql ara ari aur boo cae cam cnc cvn cma cmi cap car cas cen cep cet cha cir col com cra crb crv crt cru cyg del dor dra equ eri for gem gru her hor hya hyi ind lac leo lmi lep lib lup lyn lyr men mic mon mus nor oct oph ori pav peg per phe pic psc psa pup pyx ret sge sgr sco scl sct sex tau tel tri tra tuc uma umi vel vir vol vul".split()
FILES = [a + ".txt" for a in ABBR] + ["ser1.txt", "ser2.txt"]


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    expected = set(FILES)
    for filename in FILES:
        # The IAU archive publishes boundary filenames using uppercase
        # constellation abbreviations. Keep our repository snapshot lowercase
        # so existing Almanack consumers remain unchanged.
        remote_filename = filename.upper()
        url = f"{BASE}/{remote_filename}"
        print(f"Fetching {url} -> {filename}")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Star-Almanack/1.0 (+https://AlexanderFerrariMiller.com)"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        text = data.decode("utf-8")
        if "|" not in text:
            raise RuntimeError(f"Unexpected boundary format: {filename}")
        (DEST / filename).write_text(text, encoding="utf-8")

    actual = {p.name for p in DEST.glob("*.txt")}
    extra = actual - expected
    missing = expected - actual
    if missing or extra:
        raise RuntimeError(f"Snapshot mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    print(f"Snapshot complete: {len(actual)} boundary files")


if __name__ == "__main__":
    main()
