from __future__ import annotations

import json
from xml.sax.saxutils import escape

from lacopilot.config import get_settings
from lacopilot.tools.common import safe_output_path


def create_pdf_summary(
    title: str, sections_json: str, output_name: str = "analysis_summary.pdf"
) -> dict:
    """Create a simple local PDF from already-computed structured results.

    `sections_json`: JSON list like [{"heading":"Data Quality","body":"..."}].
    This function does not invent analysis; it only formats supplied text.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    sections = json.loads(sections_json)
    if not isinstance(sections, list):
        raise ValueError("sections_json list olmalı")
    s = get_settings()
    out = safe_output_path(output_name, ".pdf")
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(str(title)), styles["Title"]), Spacer(1, 6 * mm)]
    for sec in sections:
        if not isinstance(sec, dict):
            raise ValueError("Her section bir JSON object olmalı")
        story.append(Paragraph(escape(str(sec.get("heading", "Section"))), styles["Heading2"]))
        body = escape(str(sec.get("body", ""))).replace("\n", "<br/>")
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 4 * mm))
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(story)
    return {
        "output": str(out.resolve().relative_to(s.workspace.resolve())),
        "sections": len(sections),
    }
