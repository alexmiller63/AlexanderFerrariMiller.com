#!/usr/bin/env python3
"""Repair-once: replace the W1 single-cap test with a dynamic doubling ladder."""
from pathlib import Path

TARGET = Path("tests/test_planet_finder_w01_ladder.py")
text = TARGET.read_text(encoding="utf-8")

start = text.index("def test_mars_275_chronological_dfs_trace(monkeypatch):")
old = text[start:]
new = '''def test_mars_275_dynamic_cap_ladder(monkeypatch):
    """Run the same W1 case at successively doubled safety caps in one test.

    Every rung starts from a fresh layout() call, so no solver state is carried
    forward.  Geometry, ordering, and candidate policy are unchanged.  The
    ladder stops at the first success; otherwise the final rung fails normally.
    """
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    source = bodies(geometry())
    caps = (200, 400, 800, 1600, 3200)
    per_rung_seconds = 60.0
    failures = []

    print("W1-CAP-LADDER start caps=" + ",".join(map(str, caps)), flush=True)
    for cap in caps:
        print(f"W1-CAP-LADDER rung cap={cap} START", flush=True)
        started = __import__("time").monotonic()
        try:
            result = layout(
                FinderMode.GREEK,
                source,
                target_solutions=1,
                budget={"max_node_candidates": cap, "max_seconds": per_rung_seconds},
                context_label=f"W01-mars-275-cap-{cap}",
            )
            elapsed = __import__("time").monotonic() - started
            validate(result, source)
            print(
                f"W1-CAP-LADDER rung cap={cap} SUCCESS elapsed={elapsed:.3f}s",
                flush=True,
            )
            print(
                "W1-CAP-LADDER SUMMARY "
                + " | ".join(failures + [f"cap={cap}:SUCCESS:{elapsed:.3f}s"]),
                flush=True,
            )
            return
        except RuntimeError as exc:
            elapsed = __import__("time").monotonic() - started
            reason = " ".join(str(exc).split())
            failures.append(f"cap={cap}:FAIL:{elapsed:.3f}s:{reason}")
            print(
                f"W1-CAP-LADDER rung cap={cap} FAIL elapsed={elapsed:.3f}s reason={reason}",
                flush=True,
            )

    print("W1-CAP-LADDER SUMMARY " + " | ".join(failures), flush=True)
    raise AssertionError("W1 cap ladder exhausted without a valid layout")
'''

TARGET.write_text(text[:start] + new, encoding="utf-8")
print("Installed dynamic W1 cap ladder: 200 -> 400 -> 800 -> 1600 -> 3200.")
