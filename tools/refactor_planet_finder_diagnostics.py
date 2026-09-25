#!/usr/bin/env python3
"""Extract _solve_order's terminal diagnostics into a small support module.

This is a mechanical, behavior-preserving source transformation. It exists so
GitHub Actions can perform the large-file edit without hand-editing the 897-line
source file.
"""
from pathlib import Path

SOURCE = Path(__file__).with_name("generate_planet_finders.py")
TARGET = Path(__file__).with_name("planet_finder_diagnostics.py")


def main():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def dump_diagnostics(reason):")
    end = source.index("    def viable_candidates", start)
    block = source[start:end]
    lines = block.splitlines()
    body = "\n".join(line[4:] if line.startswith("    ") else line for line in lines[1:]) + "\n"

    module = '''"""Fixed-order Planet Finder terminal diagnostics.

Extracted mechanically from generate_planet_finders.py.
"""
from __future__ import annotations

from planet_finder_search import diagnostic_print


def dump_solver_diagnostics(
    reason, *, mode, context_label, order_index, total_orders, nodes, deepest,
    order, current_body, candidates, rejected_overlap, rejected_leader,
    rejected_route, backtracks, started, depth_residence, depth_visits,
    dead_end_visits, body_attempts, budget, diagnostic_stats, route_diagnostics,
    staged, leaders, leader_names,
):
''' + body

    wrapper = '''    def dump_diagnostics(reason):
        dump_solver_diagnostics(
            reason, mode=mode, context_label=context_label, order_index=order_index,
            total_orders=total_orders, nodes=nodes, deepest=deepest, order=order,
            current_body=current_body, candidates=candidates,
            rejected_overlap=rejected_overlap, rejected_leader=rejected_leader,
            rejected_route=rejected_route, backtracks=backtracks, started=started,
            depth_residence=depth_residence, depth_visits=depth_visits,
            dead_end_visits=dead_end_visits, body_attempts=body_attempts, budget=budget,
            diagnostic_stats=diagnostic_stats, route_diagnostics=route_diagnostics,
            staged=staged, leaders=leaders, leader_names=leader_names,
        )
'''

    source = source[:start] + wrapper + source[end:]
    import_line = "from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome, new_search_budget, layout, diagnostic_print\n"
    if "from planet_finder_diagnostics import dump_solver_diagnostics\n" not in source:
        source = source.replace(
            import_line,
            import_line + "from planet_finder_diagnostics import dump_solver_diagnostics\n",
        )

    TARGET.write_text(module, encoding="utf-8")
    SOURCE.write_text(source, encoding="utf-8")
    print(f"Wrote {TARGET} ({len(module.splitlines())} lines)")
    print(f"Reduced {SOURCE} to {len(source.splitlines())} lines")


if __name__ == "__main__":
    main()
