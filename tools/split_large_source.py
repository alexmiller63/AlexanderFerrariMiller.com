#!/usr/bin/env python3
"""Split a large text source file into small, lossless line-based chunks.

This is an inspection aid only. It does not refactor or modify the source file.
The generated manifest records hashes so the chunks can be verified and
reassembled byte-for-byte (for UTF-8 text) to confirm nothing was lost.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="UTF-8 text file to split")
    parser.add_argument("--lines", type=int, default=200,
                        help="maximum lines per chunk (default: 200)")
    parser.add_argument("--output", type=Path, default=Path(".source_chunks"),
                        help="output directory (default: .source_chunks)")
    args = parser.parse_args()

    if args.lines < 1:
        parser.error("--lines must be at least 1")
    if not args.source.is_file():
        parser.error(f"source file does not exist: {args.source}")

    raw = args.source.read_bytes()
    # Validate that this is text while preserving the original bytes exactly.
    raw.decode("utf-8")
    lines = raw.splitlines(keepends=True)

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    # Refuse to silently mix chunks from an earlier run.
    for old in out.glob("chunk_*.txt"):
        old.unlink()

    manifest = {
        "source": args.source.as_posix(),
        "source_bytes": len(raw),
        "source_lines": len(lines),
        "source_sha256": sha256(raw),
        "lines_per_chunk": args.lines,
        "chunks": [],
    }

    rebuilt = bytearray()
    for index, start in enumerate(range(0, len(lines), args.lines), start=1):
        piece = b"".join(lines[start:start + args.lines])
        name = f"chunk_{index:04d}.txt"
        path = out / name
        path.write_bytes(piece)
        rebuilt.extend(piece)
        manifest["chunks"].append({
            "file": name,
            "first_line": start + 1,
            "last_line": min(start + args.lines, len(lines)),
            "bytes": len(piece),
            "sha256": sha256(piece),
        })

    if bytes(rebuilt) != raw:
        raise RuntimeError("verification failed: reconstructed bytes differ")

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Split {args.source} into {len(manifest['chunks'])} chunks in {out}")
    print(f"Verified SHA-256: {manifest['source_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
