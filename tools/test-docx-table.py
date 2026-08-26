#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = ROOT / "test-docx-table.docx"
IMAGE_FILE = ROOT / "images" / "Alexander-Ferrari-Miller-Santa.jpeg"


def remove_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr

    borders = tblPr.first_child_found_in("w:tblBorders")

    if borders is not None:
        tblPr.remove(borders)


def main():
    document = Document()

    section = document.sections[0]

    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    usable_width = (
        section.page_width
        - section.left_margin
        - section.right_margin
    )

    table = document.add_table(rows=1, cols=2)

    table.autofit = False
    table.allow_autofit = False

    remove_table_borders(table)

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    left_width = Inches(4.75)
    right_width = usable_width - left_width

    left_cell.width = left_width
    right_cell.width = right_width

    left_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    left_paragraph = left_cell.paragraphs[0]
    left_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    name_run = left_paragraph.add_run("Alexander Ferrari Miller")
    name_run.bold = True
    name_run.font.size = Pt(18)

    left_paragraph.add_run("\n")

    profile_run = left_paragraph.add_run("Performance Profile")
    profile_run.bold = True
    profile_run.font.size = Pt(14)

    right_paragraph = right_cell.paragraphs[0]
    right_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    right_paragraph.add_run().add_picture(
        str(IMAGE_FILE),
        width=Inches(1.5),
    )

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()