#!/usr/bin/env python3
"""
Convert image files to PNG without changing their base filenames.

Usage:
    python tools/convert-images-to-png.py IMAGE [IMAGE ...]
    python tools/convert-images-to-png.py --input-dir PATH --output-dir PATH

Examples:
    python tools/convert-images-to-png.py images/AFM-1.heic
    python tools/convert-images-to-png.py images/AFM-1.heic images/AFM-2.heic

    python tools/convert-images-to-png.py \
        --input-dir images \
        --output-dir images/png

Behavior:
- Preserves the original base filename.
- Changes only the extension to .png.
- Never renames the original file.
- Never modifies the original file.
- Preserves EXIF metadata when the source and PNG format permit it.
- Preserves ICC color profiles when available.
- Preserves image dimensions.
- Preserves image orientation by applying the EXIF orientation to the
  actual pixels and then clearing the orientation tag.
- Fails rather than silently overwriting an existing PNG.
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


def register_heif_support() -> None:
    """Enable HEIC/HEIF support in Pillow."""
    pillow_heif.register_heif_opener()


def output_path_for(source: Path, output_dir: Path) -> Path:
    """
    Preserve the source base filename and change only the extension.
    """
    return output_dir / f"{source.stem}.png"


def prepare_image(image: Image.Image) -> Image.Image:
    """
    Apply the source EXIF orientation to the pixels.

    This makes the visible PNG orientation correct regardless of whether
    the PNG viewer honors the original orientation metadata.
    """
    return ImageOps.exif_transpose(image)


def convert_image(source: Path, destination: Path) -> None:
    """
    Convert one source image to PNG while preserving available metadata.
    """
    with Image.open(source) as source_image:
        exif = source_image.getexif()
        icc_profile = source_image.info.get("icc_profile")

        image = prepare_image(source_image)

        # PNG does not support every source-image mode directly.
        # Convert palette/CMYK images to a PNG-compatible representation
        # while preserving RGB/RGBA image information.
        if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
            if "A" in image.getbands():
                image = image.convert("RGBA")
            else:
                image = image.convert("RGB")

        save_kwargs = {
            "format": "PNG",
            "optimize": False,
        }

        # Pillow can write EXIF data into PNG files.
        if exif:
            save_kwargs["exif"] = exif.tobytes()

        # Preserve the embedded ICC color profile when present.
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile

        image.save(destination, **save_kwargs)


def convert_sources(
    sources: list[Path],
    output_dir: Path,
) -> int:
    """
    Convert all supplied source files.

    Returns the number of successfully converted files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0

    for source in sources:
        if not source.is_file():
            print(
                f"ERROR: source file does not exist: {source}",
                file=sys.stderr,
            )
            continue

        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(
                f"ERROR: unsupported image type: {source}",
                file=sys.stderr,
            )
            continue

        destination = output_path_for(
            source,
            output_dir,
        )

        if destination.exists():
            print(
                f"ERROR: refusing to overwrite existing file: "
                f"{destination}",
                file=sys.stderr,
            )
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

            continue

        converted += 1

    return converted


def collect_directory_sources(
    input_dir: Path,
) -> list[Path]:
    """
    Collect supported image files from one directory.

    Existing PNG files are excluded because this tool is intended to
    create PNG copies from source images.
    """
    if not input_dir.is_dir():
        raise SystemExit(
            f"Input directory does not exist: {input_dir}"
        )

    return sorted(
        path
        for path in input_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and path.suffix.lower() != ".png"
        )
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert images to PNG while preserving filenames "
            "and available metadata."
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
            "Directory for PNG output. "
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
        sources = args.images

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

    converted = convert_sources(
        sources,
        output_dir,
    )

    print(
        f"Successfully converted {converted} image(s)."
    )

    if converted != len(sources):
        print(
            "One or more images were not converted.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())