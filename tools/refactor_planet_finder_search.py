#!/usr/bin/env python3
"""Mechanically restore Planet Finder search ownership to planet_finder_search.py.

This helper deliberately edits source by AST line boundaries rather than
copying the large _solve_order implementation through an external interface.
Run from the repository root on the repair branch, then review/compile the
result before committing generated edits.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_planet_finders.py"
SEARCH = ROOT / "tools" / "planet_finder_search.py"


def function_span(text: str, name: str) -> tuple[int, int]:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node.lineno - 1, node.end_lineno
    raise RuntimeError(f"top-level function {name!r} not found")


def main() -> None:
    generator_text = GENERATOR.read_text(encoding="utf-8")
    search_text = SEARCH.read_text(encoding="utf-8")

    g_lines = generator_text.splitlines(keepends=True)
    start, end = function_span(generator_text, "_solve_order")
    solve_block = "".join(g_lines[start:end]).rstrip() + "\n\n"

    # Remove the duplicate implementation from the coordinator.
    del g_lines[start:end]
    new_generator = "".join(g_lines)

    # The modular search file historically used a temporary lazy import back
    # into the generator. Replace that shim with the exact implementation we
    # just extracted. We intentionally require a recognizable shim so this
    # script fails closed if the architecture has changed.
    marker = "def _solve_order("
    if marker in search_text:
        s_lines = search_text.splitlines(keepends=True)
        s_start, s_end = function_span(search_text, "_solve_order")
        existing = "".join(s_lines[s_start:s_end])
        if "generate_planet_finders" not in existing:
            raise RuntimeError("search already owns a non-shim _solve_order; refusing overwrite")
        s_lines[s_start:s_end] = [solve_block]
        new_search = "".join(s_lines)
    else:
        # Insert before layout(), which is the public controller that calls the
        # solver. This keeps the implementation private to the search module.
        s_lines = search_text.splitlines(keepends=True)
        layout_start, _ = function_span(search_text, "layout")
        s_lines[layout_start:layout_start] = [solve_block]
        new_search = "".join(s_lines)

    # Ensure the coordinator imports no private solver; layout remains its API.
    if "def _solve_order(" in new_generator:
        raise RuntimeError("generator still defines _solve_order after extraction")
    if "def _solve_order(" not in new_search:
        raise RuntimeError("search does not define _solve_order after extraction")

    # Parse both outputs before touching disk.
    ast.parse(new_generator)
    ast.parse(new_search)

    GENERATOR.write_text(new_generator, encoding="utf-8")
    SEARCH.write_text(new_search, encoding="utf-8")
    print("Moved _solve_order from generate_planet_finders.py to planet_finder_search.py")
    print("Both rewritten files parse successfully.")


if __name__ == "__main__":
    main()
