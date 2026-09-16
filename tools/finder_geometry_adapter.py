#!/usr/bin/env python3
"""Adapt accepted Star Almanack finder geometry to renderer path references.

The accepted geometry registry stores vertices as catalog records.  The legacy
stellar-finder renderer consumes string references such as ``HIP 113963``.
This module is the deliberately small bridge between those two contracts.
It never infers, completes, or invents geometry.
"""
from __future__ import annotations


def _vertex_ref(vertex: dict) -> str:
    catalog = str(vertex.get("catalog", "")).strip().upper()
    ident = vertex.get("id")
    if catalog != "HIP" or ident in (None, ""):
        raise RuntimeError(f"Unsupported accepted finder vertex: {vertex!r}")
    return f"HIP {int(ident)}"


def renderer_paths(record: dict) -> list[list[str]]:
    """Return accepted registry paths in render_stellar_finders format."""
    paths = record.get("paths") or []
    converted: list[list[str]] = []
    for path in paths:
        refs = [_vertex_ref(vertex) for vertex in path]
        if len(refs) < 2:
            raise RuntimeError(f"Accepted finder path has fewer than 2 vertices: {path!r}")
        converted.append(refs)
    return converted


def constellation_paths(registry: dict, abbreviation: str) -> list[list[str]]:
    figures = registry.get("constellations") or {}
    if abbreviation not in figures:
        raise RuntimeError(f"No accepted constellation geometry for {abbreviation!r}")
    record = figures[abbreviation]
    if not record.get("has_figure"):
        raise RuntimeError(f"Accepted constellation {abbreviation!r} has no drawable figure")
    paths = renderer_paths(record)
    if not paths:
        raise RuntimeError(f"Accepted constellation {abbreviation!r} has no drawable paths")
    return paths


def asterism_spec(registry: dict, asterism_id: str, fallback_name: str = "") -> dict:
    asterisms = registry.get("asterisms") or {}
    if asterism_id not in asterisms:
        raise RuntimeError(f"No accepted asterism geometry for {asterism_id!r}")
    record = asterisms[asterism_id]
    if record.get("geometry_status") != "accepted-paths":
        raise RuntimeError(f"Asterism {asterism_id!r} does not have accepted drawable paths")
    paths = renderer_paths(record)
    if not paths:
        raise RuntimeError(f"Asterism {asterism_id!r} has no drawable paths")
    return {
        "id": asterism_id,
        "name": record.get("name") or fallback_name or asterism_id,
        "paths": paths,
    }
