#!/usr/bin/env python3
"""Repair-once patch: aggregate complete-layout validation failures.

Diagnostic-only: no search, geometry, routing, budget, candidate, validation,
or controller behavior is changed. Refuse to write unless every exact target
occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")

replacements = [
    (
'''    exhausted = False

    def dump_diagnostics(reason):
''',
'''    exhausted = False
    terminal_validation_checks = 0
    terminal_validation_rejections = 0
    terminal_validation_errors = {}

    def dump_diagnostics(reason):
'''
    ),
    (
'''            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}",
                flush=True,
            )
''',
'''            validation_summary = ""
            if terminal_validation_checks:
                ranked_validation = sorted(
                    terminal_validation_errors.items(),
                    key=lambda item: (-item[1], item[0]),
                )
                validation_summary = (
                    f" terminal_validation[checks={terminal_validation_checks:,},"
                    f"rejected={terminal_validation_rejections:,},"
                    + ",".join(f"{error}={count:,}" for error, count in ranked_validation)
                    + "]"
                )
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}{validation_summary}",
                flush=True,
            )
'''
    ),
    (
'''        nonlocal nodes, deepest, candidates, backtracks, current_body
''',
'''        nonlocal nodes, deepest, candidates, backtracks, current_body
        nonlocal terminal_validation_checks, terminal_validation_rejections
'''
    ),
    (
'''                valid, errors = validate_layout(mode, result)
                if valid:
''',
'''                terminal_validation_checks += 1
                valid, errors = validate_layout(mode, result)
                if valid:
'''
    ),
    (
'''                else:
                    diagnostic_print(
                        f"Planet Finder {mode}: rejected complete layout "
''',
'''                else:
                    terminal_validation_rejections += 1
                    for error in errors:
                        terminal_validation_errors[error] = terminal_validation_errors.get(error, 0) + 1
                    diagnostic_print(
                        f"Planet Finder {mode}: rejected complete layout "
'''
    ),
]

text = TARGET.read_text(encoding="utf-8")
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Refusing repair: expected target exactly once, found {count}: {old[:80]!r}"
        )
    text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")
print("Terminal validation diagnostics added to CAPPED SUMMARY.")
