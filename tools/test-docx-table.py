#!/usr/bin/env python3

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "test-docx-table.docx"

TABLE_WIDTH_DXA = 10080
CELL_WIDTH_DXA = 5040


def get_or_add_child(parent, tag):
    child = parent.find(qn(tag))

    if child is None:
        child = OxmlElement(tag)
        parent.append(child)

    return child


def set_fixed_table_geometry(table):
    table.autofit = False
    table_properties = table._tbl.tblPr

    table_width = get_or_add_child(table_properties, "w:tblW")
    table_width.set(qn("w:type"), "dxa")
    table_width.set(qn("w:w"), str(TABLE_WIDTH_DXA))

    table_layout = get_or_add_child(table_properties, "w:tblLayout")
    table_layout.set(qn("w:type"), "fixed")

    table_indent = get_or_add_child(table_properties, "w:tblInd")
    table_indent.set(qn("w:type"), "dxa")
    table_indent.set(qn("w:w"), "0")

    table_alignment = get_or_add_child(table_properties, "w:jc")
    table_alignment.set(qn("w:val"), "left")

    cell_margins = get_or_add_child(table_properties, "w:tblCellMar")

    for margin_name in ("top", "left", "bottom", "right"):
        margin = get_or_add_child(cell_margins, f"w:{margin_name}")
        margin.set(qn("w:type"), "dxa")
        margin.set(qn("w:w"), "0")

    for grid_column in table._tbl.tblGrid.gridCol_lst:
        grid_column.set(qn("w:w"), str(CELL_WIDTH_DXA))

    for cell in table.rows[0].cells:
        cell_width = cell._tc.get_or_add_tcPr().get_or_add_tcW()
        cell_width.set(qn("w:type"), "dxa")
        cell_width.set(qn("w:w"), str(CELL_WIDTH_DXA))


def set_explicit_table_borders(table):
    table_properties = table._tbl.tblPr
    borders = get_or_add_child(table_properties, "w:tblBorders")

    for border_name in (
        "top",
        "left",
        "bottom",
        "right",
        "insideH",
        "insideV",
    ):
        border = get_or_add_child(borders, f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "12")
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "000000")


def main():
    document = Document()

    section = document.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    table = document.add_table(rows=1, cols=2)

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    left_cell.text = "Left cell Kilroy was here"
    right_cell.text = "Right cell Kilroy was here"

    right_cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    set_fixed_table_geometry(table)
    set_explicit_table_borders(table)

    document.save(OUTPUT_FILE)

    print(f"Created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()