
#!/usr/bin/env python3
"""
Generate resume output from:

  resumes/header.txt
  resumes/<name>.md

Supported output formats:
  - HTML
  - PDF
  - DOCX
  - ODT
  - TXT

Source of truth:
- header.txt = shared contact/header information
- <name>.md = resume-specific content, including an optional image
- this script = rendering/presentation only

Image policy:
- If the Markdown contains an image, the first image is treated as the
  resume portrait.
- HTML, DOCX, ODT, and PDF place that image to the right of the header.
- TXT omits images.
- The image is removed from the body so it does not appear twice.

External tools:
- Python package: markdown
- Pandoc: used for DOCX and ODT
- LibreOffice: used to convert DOCX to PDF
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    import markdown
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: markdown\n"
        "Install it with: python -m pip install markdown"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
RESUMES_DIR = ROOT / "resumes"
HEADER_FILE = RESUMES_DIR / "header.txt"
FORMATS = ("html", "pdf", "docx", "odt", "txt")


def read_header(path: Path) -> dict[str, str]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(lines) != 6:
        raise ValueError(
            f"{path} must contain exactly 6 nonblank lines:\n"
            "name, street, city/state/ZIP, phone, email, website"
        )
    return {
        "name": lines[0],
        "street": lines[1],
        "city": lines[2],
        "phone": lines[3],
        "email": lines[4],
        "website": lines[5],
    }


def validate_markdown_source(md_path: Path, md_text: str) -> None:
    if md_text.startswith("# "):
        raise ValueError(
            f"{md_path} still contains a top-level header/contact block.\n"
            "Move shared contact information to resumes/header.txt and let the "
            "Markdown begin with resume-specific content."
        )


def extract_first_image(md_text: str) -> tuple[dict[str, str] | None, str]:
    pattern = re.compile(
        r"!\[([^\]]*)\]\(([^)]+)\)"
        r"(\{[^}]*\})?",
        flags=re.MULTILINE,
    )
    match = pattern.search(md_text)
    if not match:
        return None, md_text

    image = {
        "alt": match.group(1).strip(),
        "path": match.group(2).strip(),
        "attributes": (match.group(3) or "").strip(),
    }
    body = md_text[: match.start()] + md_text[match.end() :]
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return image, body


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


def build_html(
    header: dict[str, str],
    body_html: str,
    title: str,
    image: dict[str, str] | None,
) -> str:
    name = html.escape(header["name"])
    street = html.escape(header["street"])
    city = html.escape(header["city"])
    phone = html.escape(header["phone"])
    email = html.escape(header["email"])
    website = html.escape(header["website"])
    page_title = html.escape(title)

    portrait_html = ""
    header_class = "resume-header"
    if image:
        image_path = html.escape(image["path"], quote=True)
        image_alt = html.escape(
            image["alt"] or f"{header['name']} portrait",
            quote=True,
        )
        portrait_html = f"""
                <div class="resume-portrait">
                    <img src="{image_path}" alt="{image_alt}">
                </div>"""
        header_class += " resume-header-with-image"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<style>
:root {{
    --background: #f5f5f2;
    --surface: #ffffff;
    --text: #1f2529;
    --muted: #5f686f;
    --accent: #2f536b;
    --accent-dark: #213d50;
    --border: #d9dde0;
    --max-width: 900px;
}}
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--background);
    color: var(--text);
    line-height: 1.55;
}}
.container {{ width: min(92%, var(--max-width)); margin: 0 auto; }}
.site-header {{ padding: 2rem 0 1rem; }}
.site-name {{ color: var(--accent-dark); text-decoration: none; font-weight: 700; }}
main {{ padding: 1rem 0 3rem; }}
.resume {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: clamp(1.25rem, 4vw, 2.5rem);
}}
.resume-header {{ margin-bottom: 1.5rem; }}
.resume-header-with-image {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 2rem;
    align-items: start;
}}
.resume-header h1 {{ margin: 0; color: var(--accent-dark); font-size: clamp(2rem, 6vw, 3rem); }}
.contact {{ color: var(--muted); margin: .35rem 0 0; }}
.contact a {{ color: inherit; }}
.resume-portrait {{ width: 180px; }}
.resume-portrait img {{
    display: block;
    width: 100%;
    height: auto;
    border-radius: 10px;
    border: 1px solid var(--border);
}}
.resume-body h2 {{
    color: var(--accent-dark);
    margin-top: 2rem;
    padding-bottom: .35rem;
    border-bottom: 1px solid var(--border);
    text-transform: uppercase;
    letter-spacing: .04em;
    font-size: 1rem;
}}
.resume-body h3 {{ color: var(--accent-dark); font-size: 1.15rem; margin: 1.4rem 0 .25rem; }}
.resume-body p {{ margin: .45rem 0; }}
.resume-body ul {{ margin: .35rem 0 .75rem 1.2rem; padding: 0; }}
.resume-body li {{ margin: .25rem 0; }}
.site-footer {{ border-top: 1px solid var(--border); padding: 1.5rem 0; color: var(--muted); }}
@media (max-width: 620px) {{
    .resume-header-with-image {{ grid-template-columns: 1fr; }}
    .resume-portrait {{ width: min(180px, 100%); }}
}}
@media print {{
    body {{ background: #fff; }}
    .site-header, .site-footer {{ display: none; }}
    .resume {{ border: 0; padding: 0; }}
    .resume-header-with-image {{
        grid-template-columns: minmax(0, 1fr) 150px;
        gap: 1.5rem;
    }}
    .resume-portrait {{ width: 150px; }}
}}
</style>
</head>
<body>
<header class="site-header">
    <div class="container"><a class="site-name" href="../index.html">{name}</a></div>
</header>
<main>
    <div class="container">
        <article class="resume">
            <div class="{header_class}">
                <div class="resume-contact-block">
                    <h1>{name}</h1>
                    <p class="contact">
                        {street}<br>
                        {city}<br>
                        {phone}<br>
                        <a href="mailto:{email}">{email}</a><br>
                        <a href="{website}">{website}</a>
                    </p>
                </div>
{portrait_html}
            </div>
            <div class="resume-body">
{body_html}
            </div>
        </article>
    </div>
</main>
<footer class="site-footer"><div class="container">{name}</div></footer>
</body>
</html>
"""


def build_office_html(
    header: dict[str, str],
    md_text: str,
    image: dict[str, str] | None,
) -> str:
    """
    Build HTML for DOCX and ODT.

    Using an HTML table instead of a Markdown table prevents the visible
    Contact / Portrait labels and preserves the contact-line breaks.
    PDF is generated from DOCX, so it inherits the same layout.
    """
    body_html = render_markdown(md_text)

    name = html.escape(header["name"])
    street = html.escape(header["street"])
    city = html.escape(header["city"])
    phone = html.escape(header["phone"])
    email = html.escape(header["email"])
    website = html.escape(header["website"])

    portrait = ""
    left_width = "100%"
    if image:
        left_width = "68%"
        image_path = html.escape(image["path"], quote=True)
        image_alt = html.escape(
            image["alt"] or f"{header['name']} portrait",
            quote=True,
        )
        portrait = f"""
<td style="width:32%; vertical-align:top; text-align:right;">
    <img src="{image_path}" alt="{image_alt}" style="width:1.5in; height:1.9in;">
</td>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.35; }}
table.resume-header {{ width: 100%; border-collapse: collapse; border: 0; margin: 0 0 18pt 0; }}
table.resume-header td {{ border: 0; padding: 0; }}
h2, h3 {{ color: #2f536b; }}
</style>
</head>
<body>
<table class="resume-header">
<tr>
<td style="width:{left_width}; vertical-align:top;">
    <strong>{name}</strong><br>
    {street}<br>
    {city}<br>
    {phone}<br>
    {email}<br>
    {website}
</td>
{portrait}
</tr>
</table>
{body_html}
</body>
</html>
"""


def strip_images_from_markdown(md_text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)(?:\{[^}]*\})?", "", md_text)
    text = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def markdown_to_plain_text(md_text: str) -> str:
    text = strip_images_from_markdown(md_text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*([-*_])(?:\s*\1){2,}\s*$", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*(\d+)\.\s+", r"\1. ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_txt(header: dict[str, str], md_text: str) -> str:
    body = markdown_to_plain_text(md_text)
    return (
        f'{header["name"]}\n'
        f'{header["street"]}\n'
        f'{header["city"]}\n'
        f'{header["phone"]}\n'
        f'{header["email"]}\n'
        f'{header["website"]}\n'
        f"\n{body}\n"
    )


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(
            f"Required program not found: {name}\n"
            f"Install {name} and make sure it is on PATH."
        )
    return path


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Command failed:\n" + " ".join(str(part) for part in command)
        ) from exc


def generate_html(
    stem: str,
    header: dict[str, str],
    md_text: str,
    image: dict[str, str] | None,
) -> Path:
    out_path = RESUMES_DIR / f"{stem}.html"
    body_html = render_markdown(md_text)
    title = f'{header["name"]} | {stem.replace("-", " ").title()}'
    out_path.write_text(build_html(header, body_html, title, image), encoding="utf-8")
    return out_path


def generate_txt(stem: str, header: dict[str, str], md_text: str) -> Path:
    out_path = RESUMES_DIR / f"{stem}.txt"
    out_path.write_text(build_txt(header, md_text), encoding="utf-8")
    return out_path


def generate_office(
    stem: str,
    header: dict[str, str],
    md_text: str,
    image: dict[str, str] | None,
    fmt: str,
) -> Path:
    pandoc = require_program("pandoc")
    out_path = RESUMES_DIR / f"{stem}.{fmt}"

    with tempfile.TemporaryDirectory(prefix="resume-build-") as tmp:
        tmp_dir = Path(tmp)
        source_path = tmp_dir / f"{stem}.html"
        source_path.write_text(
            build_office_html(header, md_text, image),
            encoding="utf-8",
        )

        resource_path = os.pathsep.join(
            [str(ROOT), str(RESUMES_DIR), str(ROOT / "images")]
        )

        run_checked(
            [
                pandoc,
                str(source_path),
                "--from=html",
                f"--to={fmt}",
                "--resource-path",
                resource_path,
                "-o",
                str(out_path),
            ],
            cwd=ROOT,
        )

    return out_path


def generate_docx(
    stem: str,
    header: dict[str, str],
    md_text: str,
    image: dict[str, str] | None,
) -> Path:
    return generate_office(stem, header, md_text, image, "docx")


def generate_odt(
    stem: str,
    header: dict[str, str],
    md_text: str,
    image: dict[str, str] | None,
) -> Path:
    return generate_office(stem, header, md_text, image, "odt")


def generate_pdf_from_docx(stem: str, docx_path: Path) -> Path:
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        raise SystemExit(
            "Required program not found: LibreOffice\n"
            "Install LibreOffice and make sure libreoffice or soffice is on PATH."
        )

    pdf_path = RESUMES_DIR / f"{stem}.pdf"
    with tempfile.TemporaryDirectory(prefix="resume-pdf-") as tmp:
        tmp_dir = Path(tmp)
        run_checked(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_dir),
                str(docx_path),
            ]
        )
        converted = tmp_dir / f"{stem}.pdf"
        if not converted.exists():
            raise SystemExit(
                f"LibreOffice did not create the expected PDF: {converted}"
            )
        shutil.copy2(converted, pdf_path)
    return pdf_path


def generate(stem: str, formats: list[str]) -> list[Path]:
    md_path = RESUMES_DIR / f"{stem}.md"
    if not md_path.exists():
        raise FileNotFoundError(md_path)

    header = read_header(HEADER_FILE)
    original_md = md_path.read_text(encoding="utf-8").strip()
    validate_markdown_source(md_path, original_md)
    image, body_md = extract_first_image(original_md)

    outputs: list[Path] = []
    docx_path: Path | None = None

    if "html" in formats:
        outputs.append(generate_html(stem, header, body_md, image))

    if "txt" in formats:
        outputs.append(generate_txt(stem, header, body_md))

    if "docx" in formats or "pdf" in formats:
        docx_path = generate_docx(stem, header, body_md, image)
        if "docx" in formats:
            outputs.append(docx_path)

    if "odt" in formats:
        outputs.append(generate_odt(stem, header, body_md, image))

    if "pdf" in formats:
        if docx_path is None:
            docx_path = generate_docx(stem, header, body_md, image)
        outputs.append(generate_pdf_from_docx(stem, docx_path))
        if "docx" not in formats and docx_path.exists():
            docx_path.unlink()

    return outputs


def parse_formats(value: str) -> list[str]:
    if value.lower() == "all":
        return list(FORMATS)

    requested = [
        part.strip().lower()
        for part in value.split(",")
        if part.strip()
    ]
    unknown = [fmt for fmt in requested if fmt not in FORMATS]
    if unknown:
        raise argparse.ArgumentTypeError(
            "Unknown format(s): "
            + ", ".join(unknown)
            + ". Supported: "
            + ", ".join(FORMATS)
        )
    if not requested:
        raise argparse.ArgumentTypeError("At least one output format is required.")
    return [fmt for fmt in FORMATS if fmt in requested]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "resume",
        nargs="?",
        default="performance-resume",
        help="Resume stem, e.g. performance-resume",
    )
    parser.add_argument(
        "--formats",
        type=parse_formats,
        default=parse_formats("all"),
        help="Comma-separated formats or 'all'. Default: all",
    )
    args = parser.parse_args()
    outputs = generate(args.resume, args.formats)
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()