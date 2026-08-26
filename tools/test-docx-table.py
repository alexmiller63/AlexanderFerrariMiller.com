#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "test-docx-table.docx"


def main():
    document = Document()

    section = document.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    left_cell.text = "Left cell Kilroy was here"
    right_cell.text = "Right cell Kilroy was here"

    right_cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()