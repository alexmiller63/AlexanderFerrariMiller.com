#!/usr/bin/env python3
"""One-shot: add exclusive-time profiling for alignment candidate generation."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")
old = '''    def alignment_profiled_candidates(item, depth, phase):
        """Diagnostic-only timing wrapper around viable_candidates."""
        body = item[1][1]
        key = (phase, body)
        row = alignment_phase_profile.setdefault(
            key, {"calls": 0, "elapsed": 0.0, "yielded": 0}
        )
        row["calls"] += 1
        started = time.monotonic()
        stream = viable_candidates(item, depth, consume_body_budget=False)
        try:
            for candidate in stream:
                row["yielded"] += 1
                yield candidate
        finally:
            row["elapsed"] += time.monotonic() - started
            stream.close()
'''
new = '''    def alignment_profiled_candidates(item, depth, phase):
        """Diagnostic-only *exclusive* timing around viable_candidates.

        Time only next(stream) execution.  Do not charge recursive descendant
        work to a suspended generator after it yields a candidate.
        """
        body = item[1][1]
        key = (phase, body)
        row = alignment_phase_profile.setdefault(
            key, {"calls": 0, "elapsed": 0.0, "yielded": 0}
        )
        row["calls"] += 1
        stream = viable_candidates(item, depth, consume_body_budget=False)
        try:
            while True:
                started = time.monotonic()
                try:
                    candidate = next(stream)
                except StopIteration:
                    row["elapsed"] += time.monotonic() - started
                    break
                row["elapsed"] += time.monotonic() - started
                row["yielded"] += 1
                yield candidate
        finally:
            stream.close()
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: profiled-candidate wrapper missing or non-unique")
P.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Installed exclusive-time alignment profiling; Repair Once is OFF.")
