#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = ROOT / "tools" / "test-docx-table.docx"

IMAGE_FILE = (
    ROOT
    / "images"
    / "Alexander-Ferrari-Miller-Santa.jpeg"
)


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

    # Make the table span the entire usable page width.
    table.columns[0].width = Inches(4.6)
    table.columns[1].width = usable_width - Inches(4.6)

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    left_cell.width = Inches(4.6)
    right_cell.width = usable_width - Inches(4.6)

    left_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    # ----- LEFT: CONTACT INFORMATION -----

    paragraph = left_cell.paragraphs[0]

    paragraph.paragraph_format.space_after = Pt(0)

    run = paragraph.add_run("Alexander Ferrari Miller")
    run.bold = True

    contact_lines = [
        "3549 North D Street",
        "San Bernardino, CA 92405-2103",
        "+1 (323) 681-7588",
        "Alexander.Ferrari.Miller@gmail.com",
        "https://AlexanderFerrariMiller.com",
    ]

    for line in contact_lines:
        paragraph.add_run("\n" + line)

    # ----- RIGHT: IMAGE -----

    image_paragraph = right_cell.paragraphs[0]

    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    image_paragraph.paragraph_format.space_after = Pt(0)

    if IMAGE_FILE.exists():
        image_run = image_paragraph.add_run()

        image_run.add_picture(
            str(IMAGE_FILE),
            width=Inches(1.15),
        )
    else:
        image_paragraph.add_run(
            f"[IMAGE NOT FOUND: {IMAGE_FILE}]"
        )

    remove_table_borders(table)

    # ----- TEST MARKER BELOW THE TABLE -----

    paragraph = document.add_paragraph()

    paragraph.paragraph_format.space_before = Pt(8)

    run = paragraph.add_run("TABLE TEST END")
    run.font.size = Pt(18)

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")
    print(f"Image: {IMAGE_FILE}")
    print(f"Image exists: {IMAGE_FILE.exists()}")


if __name__ == "__main__":
    main()