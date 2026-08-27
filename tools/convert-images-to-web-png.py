#!/usr/bin/env python3
"""
Create reduced-size PNG copies for website use.

Usage:
    python tools/convert-images-to-web-png.py IMAGE [IMAGE ...]
    python tools/convert-images-to-web-png.py --input-dir PATH --output-dir PATH

Examples:
    python tools/convert-images-to-web-png.py images/AFM-1.HEIC

    python tools/convert-images-to-web-png.py \
        images/AFM-1.HEIC \
        images/AFM-2.HEIC

    python tools/convert-images-to-web-png.py \
        --input-dir images \
        --output-dir images

Behavior:
- Preserves the original base filename.
- Adds "-web" before the .png extension.
- Example:
      AFM-1.HEIC -> AFM-1-web.png
- Never modifies the original file.
- Never overwrites an existing web PNG.
- Existing web PNG files are skipped normally, not treated as errors.
- When multiple source formats have the same base filename, prefers the
  original HEIC/HEIF source.
- Example:
      AFM-4.HEIC
      AFM-4.png
  Only AFM-4.HEIC is used to generate AFM-4-web.png.
- Preserves EXIF metadata when the source and PNG format permit it.
- Preserves ICC color profiles when available.
- Applies EXIF orientation to the actual pixels.
- Resizes only when the image's longest edge exceeds 1600 pixels.
- Preserves aspect ratio.
- Uses high-quality LANCZOS resampling.
- Enables PNG optimization.
- Supports HEIC/HEIF through pillow-heif.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

try:
    import pillow_heif
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pillow-heif\n"
        "Install it with: python -m pip install pillow-heif"
    ) from exc


MAX_LONG_EDGE = 1600

SUPPORTED_EXTENSIONS = {
    ".heic",
    ".heif",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
    ".bmp",
    ".gif",
    ".png",
}

# Lower number means preferred source format.
SOURCE_PREFERENCE = {
    ".heic": 0,
    ".heif": 1,
    ".jpg": 2,
    ".jpeg": 3,
    ".tif": 4,
    ".tiff": 5,
    ".webp": 6,
    ".bmp": 7,
    ".gif": 8,
    ".png": 9,
}


def register_heif_support() -> None:
    """Enable HEIC/HEIF support in Pillow."""
    pillow_heif.register_heif_opener()


def output_path_for(source: Path, output_dir: Path) -> Path:
    """
    Preserve the source base filename and add "-web.png".
    """
    return output_dir / f"{source.stem}-web.png"


def prepare_image(image: Image.Image) -> Image.Image:
    """
    Apply the source EXIF orientation to the pixels.
    """
    return ImageOps.exif_transpose(image)


def resize_for_web(image: Image.Image) -> Image.Image:
    """
    Resize an image so its longest edge is no more than MAX_LONG_EDGE.

    Images already at or below that size are returned unchanged.
    """
    width, height = image.size
    long_edge = max(width, height)

    if long_edge <= MAX_LONG_EDGE:
        return image.copy()

    scale = MAX_LONG_EDGE / long_edge

    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))

    return image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )


def convert_image(source: Path, destination: Path) -> None:
    """
    Convert one source image into a reduced-size web PNG while preserving
    available metadata.
    """
    with Image.open(source) as source_image:
        exif = source_image.getexif()
        icc_profile = source_image.info.get("icc_profile")

        image = prepare_image(source_image)
        image = resize_for_web(image)

        # PNG does not support every source-image mode directly.
        if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
            if "A" in image.getbands():
                image = image.convert("RGBA")
            else:
                image = image.convert("RGB")

        save_kwargs = {
            "format": "PNG",
            "optimize": True,
        }

        if exif:
            save_kwargs["exif"] = exif.tobytes()

        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile

        image.save(
            destination,
            **save_kwargs,
        )


def source_preference(path: Path) -> int:
    """
    Return the preference ranking for a source image.

    HEIC/HEIF originals are preferred over converted PNG copies.
    """
    return SOURCE_PREFERENCE.get(
        path.suffix.lower(),
        999,
    )


def deduplicate_sources(
    sources: list[Path],
) -> list[Path]:
    """
    Keep only one source for each base filename.

    When multiple formats share the same base filename, prefer HEIC/HEIF.

    Example:
        AFM-4.HEIC
        AFM-4.png

    becomes:
        AFM-4.HEIC
    """
    selected: dict[str, Path] = {}

    for source in sources:
        key = source.stem.lower()

        existing = selected.get(key)

        if existing is None:
            selected[key] = source
            continue

        if source_preference(source) < source_preference(existing):
            selected[key] = source

    return sorted(
        selected.values(),
        key=lambda path: path.name.lower(),
    )


def convert_sources(
    sources: list[Path],
    output_dir: Path,
) -> tuple[int, int, int]:
    """
    Convert all supplied source files.

    Returns:
        converted_count
        skipped_count
        failed_count
    """
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    converted = 0
    skipped = 0
    failed = 0

    for source in sources:
        if not source.is_file():
            print(
                f"ERROR: source file does not exist: {source}",
                file=sys.stderr,
            )
            failed += 1
            continue

        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(
                f"ERROR: unsupported image type: {source}",
                file=sys.stderr,
            )
            failed += 1
            continue

        destination = output_path_for(
            source,
            output_dir,
        )

        if destination.exists():
            print(f"Skipping existing: {destination}")
            skipped += 1
            continue

        try:
            print(f"Converting: {source}")
            print(f"       to: {destination}")

            convert_image(
                source,
                destination,
            )

        except Exception as exc:
            print(
                f"ERROR converting {source}: {exc}",
                file=sys.stderr,
            )

            if destination.exists():
                destination.unlink()

            failed += 1
            continue

        converted += 1

    return converted, skipped, failed


def collect_directory_sources(
    input_dir: Path,
) -> list[Path]:
    """
    Collect supported source images from one directory.

    Existing "-web.png" files are excluded.

    If more than one supported file has the same base filename,
    the preferred source is selected, with HEIC/HEIF taking priority.
    """
    if not input_dir.is_dir():
        raise SystemExit(
            f"Input directory does not exist: {input_dir}"
        )

    candidates = [
        path
        for path in input_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not path.stem.lower().endswith("-web")
        )
    ]

    return deduplicate_sources(candidates)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create reduced-size PNG copies for website use."
        )
    )

    parser.add_argument(
        "images",
        nargs="*",
        type=Path,
        help="Specific image files to convert.",
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing images to convert.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for web PNG output. "
            "Defaults to the input file's directory when "
            "specific files are supplied."
        ),
    )

    return parser.parse_args()


def main() -> int:
    register_heif_support()

    args = parse_arguments()

    if args.input_dir and args.images:
        print(
            "ERROR: use either specific image files or --input-dir, "
            "not both.",
            file=sys.stderr,
        )
        return 1

    if not args.input_dir and not args.images:
        print(
            "ERROR: provide image files or --input-dir.",
            file=sys.stderr,
        )
        return 1

    if args.input_dir:
        sources = collect_directory_sources(
            args.input_dir
        )

        output_dir = (
            args.output_dir
            if args.output_dir
            else args.input_dir
        )

    else:
        sources = deduplicate_sources(args.images)

        if args.output_dir:
            output_dir = args.output_dir
        else:
            parent_dirs = {
                source.resolve().parent
                for source in sources
            }

            if len(parent_dirs) != 1:
                print(
                    "ERROR: when supplying files from multiple "
                    "directories, --output-dir is required.",
                    file=sys.stderr,
                )
                return 1

            output_dir = next(iter(parent_dirs))

    print(
        f"Found {len(sources)} source image(s)."
    )

    converted, skipped, failed = convert_sources(
        sources,
        output_dir,
    )

    print(
        f"Successfully converted {converted} image(s)."
    )

    if skipped:
        print(
            f"Skipped {skipped} existing web PNG image(s)."
        )

    if failed:
        print(
            f"Failed to convert {failed} image(s).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())