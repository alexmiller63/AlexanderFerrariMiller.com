#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-docx-table.docx"

IMAGE = ROOT / "images" / "Alexander-Ferrari-Miller-Santa.jpeg"


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Required program not found: {name}")
    return path


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    pandoc = require_program("pandoc")

    if not IMAGE.exists():
        raise SystemExit(f"Image not found: {IMAGE}")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>

<table width="100%" cellspacing="0" cellpadding="0" border="0">
<tr>

<td width="80%" valign="top">
    <strong>Alexander Ferrari Miller</strong><br>
    3549 North D Street<br>
    San Bernardino, CA 92405-2103<br>
    +1 (323) 681-7588<br>
    Alexander.Ferrari.Miller@gmail.com<br>
    https://AlexanderFerrariMiller.com
</td>

<td width="20%" align="right" valign="top">
    <img
        src="{IMAGE.as_posix()}"
        alt="Alexander Ferrari Miller performing as Santa Claus"
        width="110"
    >
</td>

</tr>
</table>

<p>TABLE TEST END</p>

</body>
</html>
"""

    with tempfile.TemporaryDirectory(prefix="docx-table-test-") as tmp:
        tmp_dir = Path(tmp)
        source = tmp_dir / "test-docx-table.html"

        source.write_text(
            html,
            encoding="utf-8",
        )

        resource_path = os.pathsep.join(
            [
                str(ROOT),
                str(ROOT / "images"),
            ]
        )

        run_checked(
            [
                pandoc,
                str(source),
                "--from=html",
                "--to=docx",
                "--resource-path",
                resource_path,
                "-o",
                str(OUTPUT),
            ],
            cwd=ROOT,
        )

    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()