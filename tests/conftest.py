from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Inches
from PIL import Image, ImageDraw
import pytest


@pytest.fixture()
def sample_docx(tmp_path: Path) -> Path:
    doc_path = tmp_path / "sample.docx"
    image_path = tmp_path / "sample.png"

    img = Image.new("RGB", (220, 120), color=(245, 250, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((10, 10, 210, 110), outline=(40, 80, 160), width=3)
    draw.text((20, 45), "Wordmark", fill=(30, 50, 110))
    img.save(image_path)

    doc = Document()
    doc.add_heading("Business Document", level=1)
    doc.add_paragraph("Alpha bravo charlie. This paragraph is for comment anchoring.")
    doc.add_paragraph("Second paragraph for tracked replacement operations.")

    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Status"
    table.cell(1, 1).text = "Draft"

    doc.add_paragraph("Figure:")
    doc.add_picture(str(image_path), width=Inches(1.2))

    doc.save(doc_path)
    return doc_path
