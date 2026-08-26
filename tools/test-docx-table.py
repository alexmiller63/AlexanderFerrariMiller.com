#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = ROOT / "test-docx-table.docx"
IMAGE_FILE = ROOT / "images" / "santa.jpeg"


def remove_table_borders(table):
    tbl = table._tbl
    tbl_pr = tbl.tblPr

    borders = tbl_pr.first_child_found_in("w:tblBorders")

    if borders is not None:
        tbl_pr.remove(borders)


def main():
    document = Document()

    section = document.sections[0]

    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    # Use a full-width two-column table for the header.
    # This is more reliable in DOCX than trying to position
    # the image with spaces, tabs, or floating objects.
    table = document.add_table(rows=1, cols=2)
    table.autofit = False

    usable_width = (
        section.page_width
        - section.left_margin
        - section.right_margin
    )

    text_width = Inches(4.8)
    image_width = usable_width - text_width

    table.columns[0].width = text_width
    table.columns[1].width = image_width

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    left_cell.width = text_width
    right_cell.width = image_width

    left_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    remove_table_borders(table)

    # Left side: minimal header text.
    paragraph = left_cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_after = Pt(4)

    run = paragraph.add_run("Alexander Ferrari Miller")
    run.bold = True
    run.font.size = Pt(18)

    paragraph = left_cell.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_after = Pt(0)

    run = paragraph.add_run("Performance Profile")
    run.font.size = Pt(12)

    # Right side: put the image in the right-hand cell and
    # explicitly right-align the paragraph containing it.
    if not IMAGE_FILE.exists():
        raise FileNotFoundError(
            f"Santa image not found: {IMAGE_FILE}"
        )

    paragraph = right_cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.left_indent = Inches(0)
    paragraph.paragraph_format.right_indent = Inches(0)

    run = paragraph.add_run()
    run.add_picture(
        str(IMAGE_FILE),
        width=Inches(1.35),
    )

    document.add_paragraph()

    paragraph = document.add_paragraph()
    paragraph.add_run(
        "This is a minimal DOCX test for a header with text on "
        "the left and the Santa image aligned to the right."
    )

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()