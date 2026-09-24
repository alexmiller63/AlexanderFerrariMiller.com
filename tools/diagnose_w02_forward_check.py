#!/usr/bin/env python3
"""Instrument Planet Finder forward-check behavior, then run W36.

This diagnostic modifies only the checked-out runner copy of the generator.
It does not modify the repository generator.
"""

from pathlib import Path
import os
import subprocess
import sys


def main() -> int:
    generator = Path("tools/generate_planet_finders.py")
    text = generator.read_text(encoding="utf-8")

    old = (
        '            else:\n'
        '                body_stat["dead"] += 1\n'
        '                forward_stats["pruned"] += 1\n'
        '                return False\n'
    )
    new = (
        '            else:\n'
        '                body_stat["dead"] += 1\n'
        '                forward_stats["pruned"] += 1\n'
        '                print(f"FORWARD-CHECK DEAD future_body={future_name} future_depth={future_depth} next_depth={next_depth} raw_probes={witness_raw}", flush=True)\n'
        '                return False\n'
    )

    if old not in text:
        print("ERROR: forward-check return block not found", file=sys.stderr)
        return 2

    generator.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Forward-check diagnostic instrumentation installed.", flush=True)

    env = os.environ.copy()
    return subprocess.call(
        [sys.executable, str(generator), "--year", "2026", "--week", "36"],
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
