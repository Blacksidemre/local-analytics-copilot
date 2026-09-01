"""Verified HTML and PDF exports for deterministic Analyst findings.

Both formats are projections of an already verifier-passed ``analyst.v1``
payload. They never load source rows or calculate replacement metrics.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import reportlab
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.tools.common import safe_output_path

HTML_REPORT_SCHEMA_VERSION = "analyst-html-report.v1"
PDF_REPORT_SCHEMA_VERSION = "analyst-pdf-report.v1"
_REQUIRED_HTML_SECTIONS = {"executive-summary", "dashboard", "evidence", "methodology"}
_FONT_REGULAR = "LACVera"
_FONT_BOLD = "LACVeraBold"
_FONTS_REGISTERED = False


def _require_verified_payload(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if (
        payload.get("schema_version") != "analyst.v1"
        or payload.get("verification", {}).get("status") != "passed"
    ):
        raise ValueError("Only verifier-passed analyst.v1 payloads can produce a report")
    findings = payload.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("A verified report requires deterministic findings")
    finding_index: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("Every report finding must be an object")
        finding_id = finding.get("finding_id")
        value = finding.get("value")
        if not isinstance(finding_id, str) or not finding_id or finding_id in finding_index:
            raise ValueError("Report finding IDs must be non-empty and unique")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"Finding {finding_id} has a non-finite numeric value")
        if not isinstance(finding.get("unit"), str) or not isinstance(finding.get("source"), str):
            raise ValueError(f"Finding {finding_id} lacks typed evidence metadata")
        finding_index[finding_id] = finding
    for card in payload.get("dashboard", {}).get("cards", []):
        finding_id = card.get("finding_id") if isinstance(card, dict) else None
        expected = finding_index.get(finding_id)
        if (
            expected is None
            or card.get("value") != expected.get("value")
            or card.get("source") != expected.get("source")
        ):
            raise ValueError(f"Dashboard card is not finding-bound: {finding_id}")
    return findings, finding_index


def _manifest_digest(payload: dict[str, Any]) -> str:
    manifest = {
        "schema_version": payload["schema_version"],
        "target_semantics": payload["target_semantics"],
        "kpi_selection": payload["kpi_selection"],
        "multiple_testing": payload["multiple_testing"],
        "analyses": payload["analyses"],
        "findings": payload["findings"],
        "dashboard": payload["dashboard"],
        "interpretation": payload["interpretation"],
        "verification": payload["verification"],
    }
    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _machine_number(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".17g")


def _display_number(value: Any, unit: str) -> str:
    if unit in {"observations", "rows", "columns", "cells"}:
        return f"{int(value):,}"
    if unit in {"p_value", "adjusted_p_value"}:
        return format(float(value), ".4g")
    return format(float(value), ".5g")


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _analyses_by_effect(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {analysis["finding_ids"]["effect"]: analysis for analysis in payload.get("analyses", [])}


def _html_report(payload: dict[str, Any]) -> str:
    findings, finding_index = _require_verified_payload(payload)
    analyses = _analyses_by_effect(payload)
    cards = payload["dashboard"]["cards"]
    target = payload["target_semantics"]
    kpis = payload["kpi_selection"]
    digest = _manifest_digest(payload)
    dashboard_rows: list[str] = []
    for priority, card in enumerate(cards, start=1):
        analysis = analyses[card["finding_id"]]
        ids = analysis["finding_ids"]
        dashboard_rows.append(
            '<tr data-dashboard-card="true" '
            f'data-finding-id="{_escape(card["finding_id"])}">'
            f"<td>{priority}</td><td>{_escape(analysis['predictor'])}</td>"
            f"<td>{_escape(analysis['method'])}</td>"
            f"<td>{_escape(analysis['effect_name'])}</td>"
            f"<td>{_escape(_display_number(finding_index[ids['effect']]['value'], finding_index[ids['effect']]['unit']))}</td>"
            f"<td>{_escape(_display_number(finding_index[ids['p_value']]['value'], finding_index[ids['p_value']]['unit']))}</td>"
            f"<td>{_escape(_display_number(finding_index[ids['adjusted_p_value']]['value'], finding_index[ids['adjusted_p_value']]['unit']))}</td>"
            f"<td>{_escape(_display_number(finding_index[ids['n']]['value'], finding_index[ids['n']]['unit']))}</td>"
            f"<td><code>{_escape(card['finding_id'])}</code></td></tr>"
        )
    evidence_rows = []
    for finding in findings:
        dimension = json.dumps(
            finding.get("dimension", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        evidence_rows.append(
            '<tr data-evidence-row="true" '
            f'data-finding-id="{_escape(finding["finding_id"])}" '
            f'data-value="{_escape(_machine_number(finding["value"]))}" '
            f'data-unit="{_escape(finding["unit"])}" '
            f'data-source="{_escape(finding["source"])}">'
            f"<td><code>{_escape(finding['finding_id'])}</code></td>"
            f"<td>{_escape(finding['label'])}</td>"
            f'<td class="number">{_escape(_machine_number(finding["value"]))}</td>'
            f"<td>{_escape(finding['unit'])}</td>"
            f"<td>{_escape(finding['source'])}</td>"
            f"<td><code>{_escape(dimension)}</code></td></tr>"
        )
    interpretation = payload["interpretation"]
    interpretation_html = ""
    if interpretation.get("status") == "completed":
        evidence_ids = ", ".join(interpretation.get("evidence_finding_ids", []))
        interpretation_html = (
            "<h3>Verified local interpretation</h3>"
            f"<p>{_escape(interpretation.get('text', ''))}</p>"
            f'<p class="muted">Evidence IDs: {_escape(evidence_ids)}</p>'
        )
    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
  <meta name="lac-report-schema" content="{HTML_REPORT_SCHEMA_VERSION}">
  <meta name="lac-manifest-sha256" content="{digest}">
  <meta name="lac-finding-count" content="{len(findings)}">
  <meta name="lac-dashboard-card-count" content="{len(cards)}">
  <title>Local Analytics Copilot - Analyst Report</title>
  <style>
    :root {{ color-scheme: light; --navy:#17365d; --blue:#2f75b5; --ice:#eef5fb; --ink:#263238; --amber:#fff2cc; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,Segoe UI,Arial,sans-serif; color:var(--ink); background:#f5f7fa; line-height:1.45; }}
    main {{ max-width:1180px; margin:0 auto; padding:30px 24px 60px; }}
    header {{ color:white; background:linear-gradient(135deg,var(--navy),var(--blue)); padding:28px; border-radius:14px; }}
    h1 {{ margin:0 0 6px; font-size:28px; }} h2 {{ color:var(--navy); margin-top:32px; }} h3 {{ color:var(--blue); }}
    section {{ background:white; margin-top:18px; padding:22px; border-radius:12px; box-shadow:0 3px 14px #17365d12; }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; }}
    .fact {{ padding:14px; background:var(--ice); border-left:4px solid var(--blue); border-radius:6px; }}
    .fact strong {{ display:block; color:var(--navy); margin-bottom:4px; }}
    .warning {{ background:var(--amber); border-left:4px solid #bf9000; padding:13px; border-radius:6px; }}
    .muted {{ color:#5d6b75; font-size:13px; }}
    .table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th {{ color:white; background:var(--blue); text-align:left; }} th,td {{ padding:9px; border:1px solid #dbe4ec; vertical-align:top; }}
    tbody tr:nth-child(even) {{ background:#f7fafc; }} .number {{ text-align:right; font-variant-numeric:tabular-nums; }}
    code {{ font-family:Consolas,monospace; font-size:11px; overflow-wrap:anywhere; }}
    @media print {{ body {{ background:white; }} main {{ max-width:none; padding:0; }} section {{ box-shadow:none; break-inside:avoid; }} }}
  </style>
</head>
<body data-report-schema="{HTML_REPORT_SCHEMA_VERSION}">
<main>
  <header><h1>Local Analytics Copilot</h1><div>Verified Analyst Report</div><div class="muted" style="color:#e8f1f8">Deterministic evidence manifest: {digest}</div></header>
  <section id="executive-summary">
    <h2>Executive summary</h2>
    <div class="summary">
      <div class="fact"><strong>Target column</strong>{_escape(target["column"])}</div>
      <div class="fact"><strong>Statistical role</strong>{_escape(target["statistical_role"])}</div>
      <div class="fact"><strong>Business meaning</strong>Unverified</div>
      <div class="fact"><strong>Finding count</strong>{len(findings)}</div>
    </div>
    <p class="warning"><strong>KPI status: {_escape(kpis["status"])}</strong><br>{_escape(kpis["reason"])}</p>
  </section>
  <section id="dashboard">
    <h2>Association dashboard</h2>
    <p>{_escape(payload["dashboard"]["warning"])}</p>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>Predictor</th><th>Method</th><th>Effect</th><th>Value</th><th>Raw p</th><th>Adjusted p</th><th>Complete N</th><th>Finding ID</th></tr></thead>
    <tbody>{"".join(dashboard_rows)}</tbody></table></div>
  </section>
  <section id="evidence">
    <h2>Deterministic evidence</h2>
    <p class="muted">Every numeric row is bound to its stable finding ID, unit and calculation source.</p>
    <div class="table-wrap"><table><thead><tr><th>Finding ID</th><th>Label</th><th>Value</th><th>Unit</th><th>Source</th><th>Dimension</th></tr></thead>
    <tbody>{"".join(evidence_rows)}</tbody></table></div>
  </section>
  <section id="methodology">
    <h2>Methodology and verification</h2>
    <div class="summary">
      <div class="fact"><strong>Analyst schema</strong>{_escape(payload["schema_version"])}</div>
      <div class="fact"><strong>Multiple testing</strong>{_escape(payload["multiple_testing"]["method"])}</div>
      <div class="fact"><strong>Test family</strong>{_escape(payload["multiple_testing"]["family"])}</div>
      <div class="fact"><strong>Payload verification</strong>{_escape(payload["verification"]["status"])}</div>
      <div class="fact"><strong>Interpretation status</strong>{_escape(interpretation["status"])}</div>
    </div>
    <p class="warning">Target business meaning remains Unverified. Association is not causality, prediction or an approved KPI definition.</p>
    {interpretation_html}
  </section>
</main>
</body>
</html>
"""


class _AnalystHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.sections: set[str] = set()
        self.evidence_rows: list[dict[str, str]] = []
        self.dashboard_cards: list[dict[str, str]] = []
        self.script_count = 0
        self.external_links: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "meta" and attributes.get("name"):
            self.meta[attributes["name"]] = attributes.get("content", "")
        if tag == "section" and attributes.get("id"):
            self.sections.add(attributes["id"])
        if tag == "script":
            self.script_count += 1
        for name in ("href", "src"):
            value = attributes.get(name, "").strip()
            if value and not value.startswith(("#", "data:")):
                self.external_links.append(value)
        if tag == "tr" and attributes.get("data-evidence-row") == "true":
            self.evidence_rows.append(attributes)
        if tag == "tr" and attributes.get("data-dashboard-card") == "true":
            self.dashboard_cards.append(attributes)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data.strip())


def validate_analyst_html_report(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    findings, finding_index = _require_verified_payload(payload)
    try:
        document = path.read_text(encoding="utf-8")
        parser = _AnalystHTMLParser()
        parser.feed(document)
        parser.close()
    except Exception as exc:
        return {
            "status": "failed",
            "scope": "analyst_html_structure_manifest_evidence_and_external_resource_scan",
            "errors": [{"code": "html_open_failed", "message": str(exc)[:500]}],
            "finding_count": 0,
            "dashboard_card_count": 0,
            "external_links": [],
        }
    if not document.lstrip().lower().startswith("<!doctype html>"):
        errors.append({"code": "missing_html_doctype", "message": path.name})
    if parser.meta.get("lac-report-schema") != HTML_REPORT_SCHEMA_VERSION:
        errors.append({"code": "invalid_html_schema", "message": str(parser.meta)})
    expected_digest = _manifest_digest(payload)
    if parser.meta.get("lac-manifest-sha256") != expected_digest:
        errors.append({"code": "manifest_digest_mismatch", "message": expected_digest})
    missing_sections = sorted(_REQUIRED_HTML_SECTIONS - parser.sections)
    if missing_sections:
        errors.append({"code": "missing_html_sections", "message": ", ".join(missing_sections)})
    if parser.script_count:
        errors.append({"code": "scripts_detected", "message": str(parser.script_count)})
    if parser.external_links:
        errors.append(
            {"code": "external_links_detected", "message": ", ".join(parser.external_links[:20])}
        )

    seen: set[str] = set()
    for row in parser.evidence_rows:
        finding_id = row.get("data-finding-id", "")
        if finding_id in seen:
            errors.append({"code": "duplicate_evidence_id", "message": finding_id})
            continue
        seen.add(finding_id)
        expected = finding_index.get(finding_id)
        if expected is None:
            errors.append({"code": "unknown_evidence_id", "message": finding_id})
            continue
        try:
            same_value = math.isclose(
                float(row.get("data-value", "nan")),
                float(expected["value"]),
                rel_tol=1e-12,
                abs_tol=1e-15,
            )
        except ValueError:
            same_value = False
        if not same_value:
            errors.append({"code": "evidence_value_mismatch", "message": finding_id})
        if row.get("data-unit") != expected["unit"]:
            errors.append({"code": "evidence_unit_mismatch", "message": finding_id})
        if row.get("data-source") != expected["source"]:
            errors.append({"code": "evidence_source_mismatch", "message": finding_id})
    missing_ids = sorted(set(finding_index) - seen)
    if missing_ids:
        errors.append({"code": "missing_evidence_ids", "message": ", ".join(missing_ids[:20])})

    expected_cards = [card["finding_id"] for card in payload["dashboard"]["cards"]]
    actual_cards = [card.get("data-finding-id", "") for card in parser.dashboard_cards]
    if actual_cards != expected_cards:
        errors.append({"code": "dashboard_card_contract_mismatch", "message": str(actual_cards)})
    combined_text = " ".join(parser.text)
    if (
        payload["target_semantics"]["column"] not in combined_text
        or "Unverified" not in combined_text
    ):
        errors.append({"code": "target_semantics_missing", "message": "target or guardrail"})
    if payload["kpi_selection"]["status"] not in combined_text:
        errors.append({"code": "kpi_guardrail_missing", "message": "KPI status"})
    return {
        "status": "passed" if not errors else "failed",
        "scope": "analyst_html_structure_manifest_evidence_and_external_resource_scan",
        "errors": errors,
        "finding_count": len(parser.evidence_rows),
        "dashboard_card_count": len(parser.dashboard_cards),
        "external_links": parser.external_links,
        "manifest_sha256": parser.meta.get("lac-manifest-sha256", ""),
    }


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, font_dir / "Vera.ttf"))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, font_dir / "VeraBd.ttf"))
    _FONTS_REGISTERED = True


def _pdf_paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_escape(value).replace("\n", "<br/>"), style)


def _pdf_table_style(*, header: bool = True, font_size: float = 7.2) -> TableStyle:
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), _FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 1.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD7E3")),
        (
            "ROWBACKGROUNDS",
            (0, 1 if header else 0),
            (-1, -1),
            [colors.white, colors.HexColor("#F6F9FC")],
        ),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F75B5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
            ]
        )
    return TableStyle(commands)


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LacTitle",
            parent=base["Title"],
            fontName=_FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#17365D"),
            alignment=TA_LEFT,
            spaceAfter=5 * mm,
        ),
        "subtitle": ParagraphStyle(
            "LacSubtitle",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#44546A"),
            spaceAfter=4 * mm,
        ),
        "heading": ParagraphStyle(
            "LacHeading",
            parent=base["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=14,
            leading=17,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "LacBody",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#263238"),
        ),
        "small": ParagraphStyle(
            "LacSmall",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=6.8,
            leading=8.2,
            textColor=colors.HexColor("#263238"),
            splitLongWords=True,
            wordWrap="CJK",
        ),
        "small_bold": ParagraphStyle(
            "LacSmallBold",
            parent=base["BodyText"],
            fontName=_FONT_BOLD,
            fontSize=6.8,
            leading=8.2,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "warning": ParagraphStyle(
            "LacWarning",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#7F6000"),
            backColor=colors.HexColor("#FFF2CC"),
            borderColor=colors.HexColor("#BF9000"),
            borderWidth=0.6,
            borderPadding=7,
            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
        ),
    }


def _write_pdf_report(output: Path, payload: dict[str, Any]) -> None:
    findings, finding_index = _require_verified_payload(payload)
    _register_fonts()
    styles = _pdf_styles()
    cards = payload["dashboard"]["cards"]
    analyses = _analyses_by_effect(payload)
    digest = _manifest_digest(payload)
    page_size = landscape(A4)
    document = SimpleDocTemplate(
        str(output),
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Local Analytics Copilot - Verified Analyst Report",
        author="Local Analytics Copilot",
        subject=PDF_REPORT_SCHEMA_VERSION,
    )

    def page_frame(canvas, doc) -> None:
        canvas.saveState()
        canvas.setTitle("Local Analytics Copilot - Verified Analyst Report")
        canvas.setAuthor("Local Analytics Copilot")
        canvas.setSubject(PDF_REPORT_SCHEMA_VERSION)
        canvas.setCreator("Local Analytics Copilot deterministic report engine")
        canvas.setKeywords(f"{PDF_REPORT_SCHEMA_VERSION};lac-manifest-sha256={digest}")
        canvas.setStrokeColor(colors.HexColor("#D9E2F3"))
        canvas.line(12 * mm, 10 * mm, page_size[0] - 12 * mm, 10 * mm)
        canvas.setFont(_FONT_REGULAR, 7)
        canvas.setFillColor(colors.HexColor("#5D6B75"))
        canvas.drawString(12 * mm, 6.2 * mm, PDF_REPORT_SCHEMA_VERSION)
        canvas.drawRightString(page_size[0] - 12 * mm, 6.2 * mm, f"Page {doc.page}")
        canvas.restoreState()

    story: list[Any] = [
        _pdf_paragraph("Local Analytics Copilot", styles["title"]),
        _pdf_paragraph(
            "Verified Analyst Report - deterministic evidence only; no raw source rows are included.",
            styles["subtitle"],
        ),
        _pdf_paragraph("Executive summary", styles["heading"]),
    ]
    target = payload["target_semantics"]
    summary_rows = [
        ["Target column", target["column"], "Statistical role", target["statistical_role"]],
        ["Business meaning", "Unverified", "Deterministic findings", str(len(findings))],
        [
            "KPI status",
            payload["kpi_selection"]["status"],
            "Verification",
            payload["verification"]["status"],
        ],
    ]
    summary_table = Table(
        [[_pdf_paragraph(cell, styles["body"]) for cell in row] for row in summary_rows],
        colWidths=[33 * mm, 63 * mm, 37 * mm, 80 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_REGULAR),
                ("FONTNAME", (0, 0), (0, -1), _FONT_BOLD),
                ("FONTNAME", (2, 0), (2, -1), _FONT_BOLD),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF5FB")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD7E3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            summary_table,
            _pdf_paragraph(payload["kpi_selection"]["reason"], styles["warning"]),
            _pdf_paragraph("Association dashboard", styles["heading"]),
            _pdf_paragraph(payload["dashboard"]["warning"], styles["body"]),
            Spacer(1, 2 * mm),
        ]
    )
    dashboard_data = [
        ["#", "Predictor", "Method", "Effect", "Value", "Raw p", "Adj. p", "N", "Finding ID"]
    ]
    for priority, card in enumerate(cards, start=1):
        analysis = analyses[card["finding_id"]]
        ids = analysis["finding_ids"]
        dashboard_data.append(
            [
                str(priority),
                analysis["predictor"],
                analysis["method"],
                analysis["effect_name"],
                _display_number(
                    finding_index[ids["effect"]]["value"], finding_index[ids["effect"]]["unit"]
                ),
                _display_number(
                    finding_index[ids["p_value"]]["value"], finding_index[ids["p_value"]]["unit"]
                ),
                _display_number(
                    finding_index[ids["adjusted_p_value"]]["value"],
                    finding_index[ids["adjusted_p_value"]]["unit"],
                ),
                _display_number(finding_index[ids["n"]]["value"], finding_index[ids["n"]]["unit"]),
                card["finding_id"],
            ]
        )
    dashboard_table = LongTable(
        [
            [
                _pdf_paragraph(cell, styles["small_bold"] if row_index == 0 else styles["small"])
                for cell in row
            ]
            for row_index, row in enumerate(dashboard_data)
        ],
        colWidths=[8 * mm, 31 * mm, 25 * mm, 30 * mm, 20 * mm, 20 * mm, 20 * mm, 16 * mm, 63 * mm],
        repeatRows=1,
    )
    dashboard_table.setStyle(_pdf_table_style())
    story.extend(
        [dashboard_table, PageBreak(), _pdf_paragraph("Deterministic evidence", styles["heading"])]
    )
    evidence_data = [["Finding ID", "Label", "Value", "Unit", "Source", "Dimension"]]
    for finding in findings:
        evidence_data.append(
            [
                finding["finding_id"],
                finding["label"],
                _machine_number(finding["value"]),
                finding["unit"],
                finding["source"],
                json.dumps(finding.get("dimension", {}), ensure_ascii=False, sort_keys=True),
            ]
        )
    evidence_table = LongTable(
        [
            [
                _pdf_paragraph(cell, styles["small_bold"] if row_index == 0 else styles["small"])
                for cell in row
            ]
            for row_index, row in enumerate(evidence_data)
        ],
        colWidths=[57 * mm, 45 * mm, 25 * mm, 28 * mm, 45 * mm, 43 * mm],
        repeatRows=1,
        splitByRow=1,
    )
    evidence_table.setStyle(_pdf_table_style(font_size=6.8))
    story.extend(
        [
            evidence_table,
            PageBreak(),
            _pdf_paragraph("Methodology and verification", styles["heading"]),
        ]
    )
    methodology = [
        ("PDF report schema", PDF_REPORT_SCHEMA_VERSION),
        ("Analyst schema", payload["schema_version"]),
        ("Evidence manifest SHA-256", digest),
        ("Target selection", "Explicit user selection"),
        ("Target business meaning", "Unverified"),
        ("Multiple-testing method", payload["multiple_testing"]["method"]),
        ("Multiple-testing family", payload["multiple_testing"]["family"]),
        ("Dashboard ranking", payload["dashboard"]["ranking_basis"]),
        ("KPI status", payload["kpi_selection"]["status"]),
        ("Payload verification", payload["verification"]["status"]),
        ("Interpretation status", payload["interpretation"]["status"]),
    ]
    methodology_table = Table(
        [
            [_pdf_paragraph(key, styles["body"]), _pdf_paragraph(value, styles["body"])]
            for key, value in methodology
        ],
        colWidths=[50 * mm, 163 * mm],
    )
    methodology_table.setStyle(_pdf_table_style(header=False, font_size=8.2))
    story.extend(
        [
            methodology_table,
            _pdf_paragraph(
                "Target business meaning remains Unverified. Association is not causality, prediction or an approved KPI definition.",
                styles["warning"],
            ),
        ]
    )
    interpretation = payload["interpretation"]
    if interpretation.get("status") == "completed":
        story.extend(
            [
                _pdf_paragraph("Verified local interpretation", styles["heading"]),
                _pdf_paragraph(interpretation.get("text", ""), styles["body"]),
                Spacer(1, 2 * mm),
                _pdf_paragraph(
                    "Evidence IDs: " + ", ".join(interpretation.get("evidence_finding_ids", [])),
                    styles["small"],
                ),
            ]
        )
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value if value is not None else ""))


def validate_analyst_pdf_report(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    findings, _ = _require_verified_payload(payload)
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("Encrypted reports are not accepted")
        pages = list(reader.pages)
        text = "\n".join(page.extract_text() or "" for page in pages)
        metadata = reader.metadata or {}
    except Exception as exc:
        return {
            "status": "failed",
            "scope": "analyst_pdf_structure_manifest_evidence_and_external_link_scan",
            "errors": [{"code": "pdf_open_failed", "message": str(exc)[:500]}],
            "page_count": 0,
            "finding_count": 0,
            "dashboard_card_count": 0,
            "external_links": [],
        }
    if not pages:
        errors.append({"code": "empty_pdf", "message": path.name})
    for index, page in enumerate(pages, start=1):
        if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
            errors.append({"code": "invalid_page_box", "message": str(index)})
    title = str(metadata.get("/Title", ""))
    subject = str(metadata.get("/Subject", ""))
    keywords = str(metadata.get("/Keywords", ""))
    if title != "Local Analytics Copilot - Verified Analyst Report":
        errors.append({"code": "invalid_pdf_title", "message": title})
    if subject != PDF_REPORT_SCHEMA_VERSION:
        errors.append({"code": "invalid_pdf_schema", "message": subject})
    digest = _manifest_digest(payload)
    if f"lac-manifest-sha256={digest}" not in keywords:
        errors.append({"code": "manifest_digest_mismatch", "message": keywords})

    external_links: list[str] = []
    for page_number, page in enumerate(pages, start=1):
        annotations = page.get("/Annots") or []
        if annotations:
            external_links.append(f"page:{page_number}")
    if external_links:
        errors.append({"code": "external_links_detected", "message": ", ".join(external_links)})

    compact = _compact_text(text)
    required_text = [
        payload["target_semantics"]["column"],
        "Unverified",
        payload["kpi_selection"]["status"],
        digest,
    ]
    for required in required_text:
        if _compact_text(required) not in compact:
            errors.append({"code": "required_pdf_text_missing", "message": str(required)})
    found_ids = 0
    for finding in findings:
        finding_id = _compact_text(finding["finding_id"])
        if finding_id not in compact:
            errors.append({"code": "missing_evidence_id", "message": finding["finding_id"]})
            continue
        found_ids += 1
        for field in ("unit", "source"):
            if _compact_text(finding[field]) not in compact:
                errors.append(
                    {"code": f"evidence_{field}_missing", "message": finding["finding_id"]}
                )
        if _compact_text(_machine_number(finding["value"])) not in compact:
            errors.append({"code": "evidence_value_missing", "message": finding["finding_id"]})
    cards = payload["dashboard"]["cards"]
    return {
        "status": "passed" if not errors else "failed",
        "scope": "analyst_pdf_structure_manifest_evidence_and_external_link_scan",
        "errors": errors,
        "page_count": len(pages),
        "finding_count": found_ids,
        "dashboard_card_count": len(cards),
        "external_links": external_links,
        "manifest_sha256": digest,
    }


def _report_result(
    output: Path,
    payload: dict[str, Any],
    schema_version: str,
    media_type: str,
    verification: dict[str, Any],
    audit_event: str,
) -> dict[str, Any]:
    if verification["status"] != "passed":
        output.unlink(missing_ok=True)
        raise RuntimeError(f"Analyst report verification failed: {verification['errors'][:3]}")
    settings = get_settings()
    relative_output = str(output.resolve().relative_to(settings.workspace.resolve()))
    audit(
        settings.logs_dir,
        audit_event,
        output=relative_output,
        target=payload["target_semantics"]["column"],
        findings=verification["finding_count"],
    )
    return {
        "status": "created",
        "schema_version": schema_version,
        "output": relative_output,
        "filename": output.name,
        "media_type": media_type,
        "verification": verification,
    }


def create_analyst_html_report(
    payload: dict[str, Any], output_name: str = "analyst_report.html"
) -> dict[str, Any]:
    _require_verified_payload(payload)
    output = safe_output_path(output_name, ".html")
    output.write_text(_html_report(payload), encoding="utf-8", newline="\n")
    verification = validate_analyst_html_report(output, payload)
    return _report_result(
        output,
        payload,
        HTML_REPORT_SCHEMA_VERSION,
        "text/html; charset=utf-8",
        verification,
        "analyst_html_report",
    )


def create_analyst_pdf_report(
    payload: dict[str, Any], output_name: str = "analyst_report.pdf"
) -> dict[str, Any]:
    _require_verified_payload(payload)
    output = safe_output_path(output_name, ".pdf")
    _write_pdf_report(output, payload)
    verification = validate_analyst_pdf_report(output, payload)
    return _report_result(
        output,
        payload,
        PDF_REPORT_SCHEMA_VERSION,
        "application/pdf",
        verification,
        "analyst_pdf_report",
    )
