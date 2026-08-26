from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


OUTPUT = "test-docx-table.docx"
SANTA_IMAGE = "images/santa.jpeg"


doc = Document()

section = doc.sections[0]

usable_width = (
    section.page_width
    - section.left_margin
    - section.right_margin
)

table = doc.add_table(rows=1, cols=2)
table.autofit = False
table.alignment = WD_TABLE_ALIGNMENT.LEFT

left_cell = table.cell(0, 0)
right_cell = table.cell(0, 1)

left_width = Inches(5.0)
right_width = usable_width - left_width

left_cell.width = left_width
right_cell.width = right_width


def set_cell_width(cell, width):
    tc_pr = cell._tc.get_or_add_tcPr()

    tc_w = tc_pr.first_child_found_in("w:tcW")
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)

    tc_w.set(qn("w:w"), str(int(width / 635)))
    tc_w.set(qn("w:type"), "dxa")


set_cell_width(left_cell, left_width)
set_cell_width(right_cell, right_width)

# Contact information — left cell
p = left_cell.paragraphs[0]
p.add_run("Alexander Ferrari Miller")

for line in [
    "3549 North D Street",
    "San Bernardino, CA 92405-2103",
    "+1 (323) 681-7588",
    "Alexander.Ferrari.Miller@gmail.com",
    "https://AlexanderFerrariMiller.com",
]:
    p = left_cell.add_paragraph(line)

# Santa — right cell
right_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

p = right_cell.paragraphs[0]
p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

run = p.add_run()
run.add_picture(SANTA_IMAGE, width=Inches(1.5))

# Test marker below the complete table
doc.add_paragraph("TABLE TEST END")

doc.save(OUTPUT)

print(f"Created {OUTPUT}")