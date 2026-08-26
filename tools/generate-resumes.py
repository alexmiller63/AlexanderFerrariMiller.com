#!/usr/bin/env python3
"""
Generate HTML resumes from:
  resumes/header.txt
  resumes/<name>.md

Source of truth:
- header.txt = shared contact/header information
- <name>.md = resume-specific content, including image references
- this script = rendering/presentation only
"""

from __future__ import annotations

import argparse
import html
import re
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


def read_header(path: Path) -> dict[str, str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

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


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


def add_resume_image_class(body_html: str) -> str:
    return re.sub(
        r"<img(?![^>]*\bclass=)",
        '<img class="resume-image"',
        body_html,
    )


def build_html(header: dict[str, str], body_html: str, title: str) -> str:
    name = html.escape(header["name"])
    street = html.escape(header["street"])
    city = html.escape(header["city"])
    phone = html.escape(header["phone"])
    email = html.escape(header["email"])
    website = html.escape(header["website"])
    page_title = html.escape(title)

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
.container {{
    width: min(92%, var(--max-width));
    margin: 0 auto;
}}
.site-header {{
    padding: 2rem 0 1rem;
}}
.site-name {{
    color: var(--accent-dark);
    text-decoration: none;
    font-weight: 700;
}}
main {{
    padding: 1rem 0 3rem;
}}
.resume {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: clamp(1.25rem, 4vw, 2.5rem);
}}
.resume-header {{
    margin-bottom: 1.5rem;
}}
.resume-header h1 {{
    margin: 0;
    color: var(--accent-dark);
    font-size: clamp(2rem, 6vw, 3rem);
}}
.contact {{
    color: var(--muted);
    margin: .35rem 0 0;
}}
.contact a {{
    color: inherit;
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
.resume-body h3 {{
    color: var(--accent-dark);
    font-size: 1.15rem;
    margin: 1.4rem 0 .25rem;
}}
.resume-body p {{
    margin: .45rem 0;
}}
.resume-body ul {{
    margin: .35rem 0 .75rem 1.2rem;
    padding: 0;
}}
.resume-body li {{
    margin: .25rem 0;
}}
.resume-image {{
    display: block;
    width: min(100%, 230px);
    height: auto;
    border-radius: 10px;
    border: 1px solid var(--border);
    margin: 1rem 0 1.5rem;
}}
.site-footer {{
    border-top: 1px solid var(--border);
    padding: 1.5rem 0;
    color: var(--muted);
}}
@media print {{
    body {{ background: #fff; }}
    .site-header, .site-footer {{ display: none; }}
    .resume {{ border: 0; padding: 0; }}
    .resume-image {{ width: 150px; }}
}}
</style>
</head>
<body>
<header class="site-header">
    <div class="container">
        <a class="site-name" href="../index.html">{name}</a>
    </div>
</header>

<main>
    <div class="container">
        <article class="resume">
            <div class="resume-header">
                <h1>{name}</h1>
                <p class="contact">
                    {street}<br>
                    {city}<br>
                    {phone}<br>
                    <a href="mailto:{email}">{email}</a><br>
                    <a href="{website}">{website}</a>
                </p>
            </div>

            <div class="resume-body">
{body_html}
            </div>
        </article>
    </div>
</main>

<footer class="site-footer">
    <div class="container">{name}</div>
</footer>
</body>
</html>
"""


def generate(stem: str) -> Path:
    md_path = RESUMES_DIR / f"{stem}.md"
    out_path = RESUMES_DIR / f"{stem}.html"

    if not md_path.exists():
        raise FileNotFoundError(md_path)

    header = read_header(HEADER_FILE)
    md_text = md_path.read_text(encoding="utf-8").strip()

    if md_text.startswith("# "):
        raise ValueError(
            f"{md_path} still contains a top-level header/contact block.\n"
            "Move shared contact information to resumes/header.txt and let the "
            "Markdown begin with resume-specific content."
        )

    body_html = add_resume_image_class(render_markdown(md_text))
    title = f'{header["name"]} | {stem.replace("-", " ").title()}'
    out_path.write_text(build_html(header, body_html, title), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "resume",
        nargs="?",
        default="performance-resume",
        help="Resume stem, e.g. performance-resume",
    )
    args = parser.parse_args()
    output = generate(args.resume)
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
