#!/usr/bin/env python3
"""Split or reassemble planet_finder_search_core.py losslessly.

This is deliberately a mechanical source-management tool, not a refactor.
Split mode copies contiguous line ranges into numbered text chunks plus a
manifest and verifies that concatenating the chunks reproduces the source.
Reassemble mode concatenates the manifest-listed chunks back into the canonical
source and verifies each chunk against its manifest hash before writing.

Usage:
    python tools/split_planet_finder_source.py
    python tools/split_planet_finder_source.py --lines 250
    python tools/split_planet_finder_source.py --reassemble

Generated files live under tools/planet_finder_chunks/. The canonical executable
remains tools/generate_planet_finders.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tools" / "planet_finder_search_core.py"
DEFAULT_OUTPUT = ROOT / "tools" / "planet_finder_chunks"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_source(source: Path, output: Path, lines_per_chunk: int) -> None:
    if lines_per_chunk < 1:
        raise ValueError("lines_per_chunk must be positive")

    original = source.read_bytes()
    lines = original.splitlines(keepends=True)
    output.mkdir(parents=True, exist_ok=True)

    for old in output.glob("chunk-*.txt"):
        old.unlink()

    manifest = {
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(original),
        "line_count": len(lines),
        "lines_per_chunk": lines_per_chunk,
        "chunks": [],
    }

    rebuilt = bytearray()
    for index, start in enumerate(range(0, len(lines), lines_per_chunk), 1):
        chunk_lines = lines[start:start + lines_per_chunk]
        payload = b"".join(chunk_lines)
        name = f"chunk-{index:03d}.txt"
        (output / name).write_bytes(payload)
        rebuilt.extend(payload)
        manifest["chunks"].append({
            "file": name,
            "start_line": start + 1,
            "end_line": start + len(chunk_lines),
            "sha256": sha256(payload),
        })

    if bytes(rebuilt) != original:
        raise RuntimeError("lossless reconstruction check failed")

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Split {manifest['source']} into {len(manifest['chunks'])} chunks; "
        f"lossless SHA-256 verification passed."
    )


def reassemble_source(source: Path, output: Path) -> None:
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rebuilt = bytearray()
    line_count = 0

    for entry in manifest["chunks"]:
        chunk_path = output / entry["file"]
        payload = chunk_path.read_bytes()
        actual_hash = sha256(payload)
        if actual_hash != entry["sha256"]:
            raise RuntimeError(
                f"chunk hash mismatch for {entry['file']}: "
                f"manifest={entry['sha256']} actual={actual_hash}. "
                "Update the manifest deliberately after editing a chunk."
            )
        rebuilt.extend(payload)
        line_count += len(payload.splitlines(keepends=True))

    if line_count != manifest["line_count"]:
        raise RuntimeError(
            f"line-count mismatch: manifest={manifest['line_count']} actual={line_count}"
        )

    source.write_bytes(bytes(rebuilt))
    actual_source_hash = sha256(bytes(rebuilt))
    print(
        f"Reassembled {source.relative_to(ROOT).as_posix()} from "
        f"{len(manifest['chunks'])} verified chunks; SHA-256={actual_source_hash}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lines", type=int, default=250,
                        help="maximum source lines per chunk (default: 250)")
    parser.add_argument("--reassemble", action="store_true",
                        help="rebuild canonical source from manifest-listed chunks")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if args.reassemble:
        reassemble_source(source, output)
    else:
        split_source(source, output, args.lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
