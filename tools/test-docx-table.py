#!/usr/bin/env python3

from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "test-docx-table.docx"


def main():
    document = Document()

    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"

    table.cell(0, 0).text = "Left cell Kilroy was here"
    table.cell(0, 1).text = "Right cell Kilroy was here"

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()