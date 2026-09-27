#!/usr/bin/env python3
"""Repair-once patch: identify leaders that collide with the Sun label.

Diagnostic-only: no search, geometry, routing, budget, candidate, validation,
or controller behavior is changed. Refuse to write unless every exact target
occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")

replacements = [
    (
'''    terminal_validation_checks = 0
    terminal_validation_rejections = 0
    terminal_validation_errors = {}
''',
'''    terminal_validation_checks = 0
    terminal_validation_rejections = 0
    terminal_validation_errors = {}
    terminal_validation_sun_leaders = {}
'''
    ),
    (
'''                validation_summary = (
                    f" terminal_validation[checks={terminal_validation_checks:,},"
                    f"rejected={terminal_validation_rejections:,},"
                    + ",".join(f"{error}={count:,}" for error, count in ranked_validation)
                    + "]"
                )
''',
'''                validation_summary = (
                    f" terminal_validation[checks={terminal_validation_checks:,},"
                    f"rejected={terminal_validation_rejections:,},"
                    + ",".join(f"{error}={count:,}" for error, count in ranked_validation)
                    + "]"
                )
                if terminal_validation_sun_leaders:
                    ranked_sun_leaders = sorted(
                        terminal_validation_sun_leaders.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                    validation_summary += (
                        " sun_label_hit_by["
                        + ",".join(
                            f"{name}={count:,}" for name, count in ranked_sun_leaders
                        )
                        + "]"
                    )
'''
    ),
    (
'''        nonlocal terminal_validation_checks, terminal_validation_rejections
''',
'''        nonlocal terminal_validation_checks, terminal_validation_rejections
        nonlocal terminal_validation_sun_leaders
'''
    ),
    (
'''                    for error in errors:
                        terminal_validation_errors[error] = terminal_validation_errors.get(error, 0) + 1
''',
'''                    for error in errors:
                        terminal_validation_errors[error] = terminal_validation_errors.get(error, 0) + 1
                        suffix = ": leader crosses Sun label"
                        if error.endswith(suffix):
                            leader_name = error[:-len(suffix)]
                            terminal_validation_sun_leaders[leader_name] = (
                                terminal_validation_sun_leaders.get(leader_name, 0) + 1
                            )
'''
    ),
]

text = TARGET.read_text(encoding="utf-8")
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Refusing repair: expected target exactly once, found {count}: {old[:100]!r}"
        )
    text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")
print("Sun-label leader identity diagnostics added to CAPPED SUMMARY.")