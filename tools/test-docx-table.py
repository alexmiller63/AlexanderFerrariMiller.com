#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "test-docx-table.docx"


def remove_table_borders(table):
    table_properties = table._tbl.tblPr
    borders = table_properties.first_child_found_in("w:tblBorders")

    if borders is not None:
        table_properties.remove(borders)


def set_table_grid_widths(table, widths):
    table_grid = table._tbl.tblGrid

    for child in list(table_grid):
        table_grid.remove(child)

    for width in widths:
        grid_column = OxmlElement("w:gridCol")
        grid_column.set(qn("w:w"), str(width.twips))
        table_grid.append(grid_column)


def set_cell_width(cell, width):
    cell.width = width

    cell_properties = cell._tc.get_or_add_tcPr()
    cell_width = cell_properties.first_child_found_in("w:tcW")

    if cell_width is None:
        cell_width = OxmlElement("w:tcW")
        cell_properties.append(cell_width)

    cell_width.set(qn("w:w"), str(width.twips))
    cell_width.set(qn("w:type"), "dxa")


def main():
    document = Document()

    section = document.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    table = document.add_table(rows=1, cols=2)
    table.autofit = False
    table.allow_autofit = False

    left_width = Inches(5.0)
    right_width = Inches(2.0)

    table.columns[0].width = left_width
    table.columns[1].width = right_width

    set_table_grid_widths(table, [left_width, right_width])

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    set_cell_width(left_cell, left_width)
    set_cell_width(right_cell, right_width)

    left_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    right_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    left_paragraph = left_cell.paragraphs[0]
    left_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    left_paragraph.paragraph_format.space_after = Pt(0)
    left_paragraph.add_run("Left cell")

    right_paragraph = right_cell.paragraphs[0]
    right_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_paragraph.paragraph_format.space_after = Pt(0)
    right_paragraph.add_run("Kilroy was here")

    remove_table_borders(table)

    document.save(OUTPUT_FILE)
    print(f"Created {OUTPUT_FILE}")


if __name__ == "__main__":
    main()