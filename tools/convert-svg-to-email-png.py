#!/usr/bin/env python3
"""
Create email-safe PNG derivatives from SVG source artwork.

Usage:
    python tools/convert-svg-to-email-png.py SVG [SVG ...]
    python tools/convert-svg-to-email-png.py --input-dir PATH --output-dir PATH

Behavior:
- Accepts SVG source files only.
- Preserves the source base filename.
- Adds "-email" before the .png extension.
- Example: address.svg -> address-email.png
- Never modifies the source SVG.
- Never overwrites an existing email PNG unless --overwrite is supplied.
- Renders at 4x the intended display size by default for crisp Retina output.
- Uses CairoSVG for standards-compliant SVG rasterization.
- Preserves artwork colors and any white tile/background already present in the SVG.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import cairosvg
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: cairosvg\n"
        "Install it with: python -m pip install cairosvg"
    ) from exc


DEFAULT_DISPLAY_SIZE = 13
DEFAULT_SCALE = 4


def output_path_for(source: Path, output_dir: Path) -> Path:
    return output_dir / f"{source.stem}-email.png"


def convert_svg(
    source: Path,
    destination: Path,
    display_size: int,
    scale: int,
) -> None:
    output_size = display_size * scale

    cairosvg.svg2png(
        url=str(source),
        write_to=str(destination),
        output_width=output_size,
        output_height=output_size,
    )


def collect_directory_sources(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    return sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".svg"
        ),
        key=lambda path: path.name.lower(),
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create email-safe PNG derivatives from SVG artwork."
    )

    parser.add_argument(
        "svgs",
        nargs="*",
        type=Path,
        help="Specific SVG files to convert.",
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing SVG files to convert.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for email PNG output. Defaults to the source "
            "directory when specific files are supplied, or to --input-dir."
        ),
    )

    parser.add_argument(
        "--display-size",
        type=int,
        default=DEFAULT_DISPLAY_SIZE,
        help=(
            f"Intended displayed width/height in pixels; default "
            f"{DEFAULT_DISPLAY_SIZE}."
        ),
    )

    parser.add_argument(
        "--scale",
        type=int,
        default=DEFAULT_SCALE,
        help=f"Raster scale factor; default {DEFAULT_SCALE}.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing -email.png files.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    if args.input_dir and args.svgs:
        print(
            "ERROR: use either specific SVG files or --input-dir, not both.",
            file=sys.stderr,
        )
        return 1

    if not args.input_dir and not args.svgs:
        print(
            "ERROR: provide SVG files or --input-dir.",
            file=sys.stderr,
        )
        return 1

    if args.display_size < 1 or args.scale < 1:
        print(
            "ERROR: --display-size and --scale must both be positive integers.",
            file=sys.stderr,
        )
        return 1

    if args.input_dir:
        sources = collect_directory_sources(args.input_dir)
        output_dir = args.output_dir or args.input_dir
    else:
        sources = sorted(args.svgs, key=lambda path: path.name.lower())

        if args.output_dir:
            output_dir = args.output_dir
        else:
            parent_dirs = {source.resolve().parent for source in sources}

            if len(parent_dirs) != 1:
                print(
                    "ERROR: when supplying files from multiple directories, "
                    "--output-dir is required.",
                    file=sys.stderr,
                )
                return 1

            output_dir = next(iter(parent_dirs))

    output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    failed = 0

    for source in sources:
        if not source.is_file():
            print(f"ERROR: source file does not exist: {source}", file=sys.stderr)
            failed += 1
            continue

        if source.suffix.lower() != ".svg":
            print(f"ERROR: source is not SVG: {source}", file=sys.stderr)
            failed += 1
            continue

        destination = output_path_for(source, output_dir)

        if destination.exists() and not args.overwrite:
            print(f"Skipping existing: {destination}")
            skipped += 1
            continue

        try:
            print(f"Converting: {source}")
            print(f"       to: {destination}")

            convert_svg(
                source,
                destination,
                args.display_size,
                args.scale,
            )
        except Exception as exc:
            print(f"ERROR converting {source}: {exc}", file=sys.stderr)

            if destination.exists():
                destination.unlink()

            failed += 1
            continue

        converted += 1

    print(f"Successfully converted {converted} SVG(s).")

    if skipped:
        print(f"Skipped {skipped} existing email PNG(s).")

    if failed:
        print(f"Failed to convert {failed} SVG(s).", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
