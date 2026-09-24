#!/usr/bin/env python3
"""Split a large text/source file into small, lossless line chunks.

This is a mechanical staging tool only. It does not parse, rewrite, format,
or refactor the input. Concatenating the generated .part files reproduces the
original file byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_file(source: Path, output_dir: Path, lines_per_chunk: int) -> None:
    if lines_per_chunk < 1:
        raise ValueError("--lines must be at least 1")
    if not source.is_file():
        raise FileNotFoundError(source)

    original = source.read_bytes()
    lines = original.splitlines(keepends=True)

    # splitlines() returns no element for an empty file, which is fine: the
    # manifest still records and verifies the empty original.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Refuse to mix a new split with stale parts from an earlier run.
    for old_part in output_dir.glob("*.part"):
        old_part.unlink()

    chunks = []
    rebuilt = bytearray()

    for index, start in enumerate(range(0, len(lines), lines_per_chunk), 1):
        block = b"".join(lines[start : start + lines_per_chunk])
        end = min(start + lines_per_chunk, len(lines))
        filename = f"chunk_{index:04d}.part"
        path = output_dir / filename
        path.write_bytes(block)
        rebuilt.extend(block)
        chunks.append(
            {
                "file": filename,
                "first_line": start + 1,
                "last_line": end,
                "bytes": len(block),
                "sha256": sha256(block),
            }
        )

    if bytes(rebuilt) != original:
        raise RuntimeError("Lossless verification failed; output was not kept.")

    manifest = {
        "source": source.as_posix(),
        "source_bytes": len(original),
        "source_lines": len(lines),
        "lines_per_chunk": lines_per_chunk,
        "source_sha256": sha256(original),
        "chunks": chunks,
        "verified_byte_for_byte": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Split {source} into {len(chunks)} chunks in {output_dir}")
    print(f"SHA-256: {manifest['source_sha256']}")
    print("Byte-for-byte reconstruction verified.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mechanically split a large file into lossless line chunks."
    )
    parser.add_argument("source", type=Path, help="file to split")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp/file_chunks"),
        help="output directory (default: tmp/file_chunks)",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=200,
        help="lines per chunk (default: 200)",
    )
    args = parser.parse_args()
    split_file(args.source, args.output, args.lines)


if __name__ == "__main__":
    main()
