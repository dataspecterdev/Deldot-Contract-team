"""PDF Summary Report — professional findings report separated by contract.

Generates a multi-page PDF with:
- Cover page with overall summary
- Per-package sections with findings tables
- Color-coded severity (Critical=red, High=orange, Medium=yellow, Info=green)
- Exact file/page/line references for each finding
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

from .checklist import requirement_map
from .config import FLAG, NO_FLAG
from .models import ContractPackage, Finding

# Colors for severity levels
SEVERITY_COLORS = {
    "Critical": colors.Color(0.86, 0.15, 0.15),  # red
    "High": colors.Color(0.85, 0.45, 0.02),      # orange
    "Medium": colors.Color(0.75, 0.65, 0.0),     # amber
    "Low": colors.Color(0.3, 0.6, 0.3),          # muted green
    "Info": colors.Color(0.4, 0.5, 0.6),         # slate
}

SEVERITY_BG = {
    "Critical": colors.Color(1.0, 0.9, 0.9),
    "High": colors.Color(1.0, 0.94, 0.88),
    "Medium": colors.Color(1.0, 0.97, 0.88),
    "Low": colors.Color(0.92, 0.97, 0.92),
    "Info": colors.Color(0.94, 0.96, 0.98),
}


def _build_styles():
    """Create custom paragraph styles for the report."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=28,
        spaceAfter=6,
        textColor=colors.Color(0.1, 0.15, 0.27),
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.Color(0.4, 0.45, 0.5),
        spaceAfter=30,
    ))
    styles.add(ParagraphStyle(
        "PackageTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.Color(0.1, 0.15, 0.27),
        spaceBefore=20,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "FindingTitle",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.Color(0.17, 0.32, 0.51),
        spaceBefore=14,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "Evidence",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Courier",
        leftIndent=12,
        textColor=colors.Color(0.3, 0.3, 0.3),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.Color(0.4, 0.45, 0.5),
    ))
    styles.add(ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.Color(0.5, 0.5, 0.5),
        alignment=1,  # center
    ))
    return styles


def _severity_badge(severity: str, styles) -> Paragraph:
    color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["Info"])
    hex_color = f"#{int(color.red*255):02x}{int(color.green*255):02x}{int(color.blue*255):02x}"
    return Paragraph(
        f'<font color="{hex_color}"><b>{severity}</b></font>',
        styles["Body"],
    )


def _truncate(text: str, max_len: int = 300) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _build_cover_page(findings: list[Finding], packages: dict[str, ContractPackage], styles) -> list:
    """Build the cover page elements."""
    elements = []

    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph("DORA", styles["CoverTitle"]))
    elements.append(Paragraph(
        "DelDOT Orchestrated Review Assistant — Findings Report",
        styles["CoverSubtitle"],
    ))

    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    elements.append(Paragraph(f"Generated: {now}", styles["Body"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Summary stats
    total = len(findings)
    flags = sum(1 for f in findings if f.predicted_label == FLAG)
    compliant = total - flags
    num_packages = len(packages)

    summary_data = [
        ["Metric", "Value"],
        ["Packages Analyzed", str(num_packages)],
        ["Total Requirements Checked", str(total)],
        ["Findings (FLAG)", str(flags)],
        ["Compliant (NO_FLAG)", str(compliant)],
    ]

    # Severity breakdown for flags
    by_sev: dict[str, int] = {}
    for f in findings:
        if f.predicted_label == FLAG:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    for sev in ["Critical", "High", "Medium", "Low"]:
        if sev in by_sev:
            summary_data.append([f"  {sev} Flags", str(by_sev[sev])])

    t = Table(summary_data, colWidths=[2.5 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.1, 0.15, 0.27)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.Color(0.97, 0.97, 0.98), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "Scoring Authority: Reference_Checklist.csv — Challenge_Reference_Rule",
        styles["Label"],
    ))
    elements.append(Paragraph(
        "Sources (.txt files) are used for confidence scoring only, not as validation criteria.",
        styles["Label"],
    ))

    elements.append(Spacer(1, 2 * inch))
    elements.append(Paragraph(
        "This is not an official DelDOT application. Findings are decision support only — "
        "not a legal conclusion. Human review is required.",
        styles["Disclaimer"],
    ))

    elements.append(PageBreak())
    return elements


def _build_package_section(
    package_id: str,
    pkg_findings: list[Finding],
    package: ContractPackage | None,
    req_map: dict[str, Any],
    styles,
) -> list:
    """Build a section for one contract package."""
    elements = []

    # Package header
    title = package_id.replace("-", " ").replace("_", " ")
    flags = [f for f in pkg_findings if f.predicted_label == FLAG]
    compliant = [f for f in pkg_findings if f.predicted_label == NO_FLAG]

    elements.append(Paragraph(f"Contract: {title}", styles["PackageTitle"]))
    elements.append(Paragraph(
        f"{len(pkg_findings)} requirements checked — "
        f"<b>{len(flags)} flag{'s' if len(flags) != 1 else ''}</b>, "
        f"{len(compliant)} compliant",
        styles["Body"],
    ))
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.Color(0.85, 0.85, 0.85),
        spaceBefore=4, spaceAfter=12,
    ))

    # FLAGS first
    if flags:
        elements.append(Paragraph("<b>Flagged Findings</b>", styles["Body"]))
        elements.append(Spacer(1, 4))

        for finding in sorted(flags, key=lambda f: f.requirement_id):
            req = req_map.get(finding.requirement_id)
            req_name = req.name if req else finding.requirement_id
            elements.append(Paragraph(
                f"{finding.requirement_id} — {req_name}",
                styles["FindingTitle"],
            ))

            # Severity and location
            sev_color = SEVERITY_COLORS.get(finding.severity, SEVERITY_COLORS["Info"])
            hex_c = f"#{int(sev_color.red*255):02x}{int(sev_color.green*255):02x}{int(sev_color.blue*255):02x}"
            elements.append(Paragraph(
                f'Severity: <font color="{hex_c}"><b>{finding.severity}</b></font> '
                f'&nbsp;&nbsp;|&nbsp;&nbsp; Confidence: {finding.confidence:.0%} '
                f'&nbsp;&nbsp;|&nbsp;&nbsp; Governing: {finding.governing_document}',
                styles["Label"],
            ))

            # Location
            if finding.draft_location:
                elements.append(Paragraph(
                    f"Location: {finding.draft_location}",
                    styles["Label"],
                ))

            # What the contract says
            if finding.draft_evidence:
                elements.append(Spacer(1, 3))
                elements.append(Paragraph("Contract says:", styles["Label"]))
                safe_evidence = _truncate(finding.draft_evidence).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(f'"{safe_evidence}"', styles["Evidence"]))

            # What the rule requires
            if req and req.challenge_reference_rule:
                elements.append(Paragraph("Rule requires:", styles["Label"]))
                safe_rule = _truncate(req.challenge_reference_rule).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(safe_rule, styles["Evidence"]))

            # Explanation
            if finding.explanation:
                elements.append(Spacer(1, 3))
                safe_expl = _truncate(finding.explanation, 400).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(safe_expl, styles["Body"]))

            # Recommended action
            if finding.recommended_human_action:
                safe_action = _truncate(finding.recommended_human_action, 200).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(
                    f'<i>Action: {safe_action}</i>',
                    styles["Body"],
                ))

            elements.append(Spacer(1, 8))

    # Compliant items as a compact table
    if compliant:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Compliant Requirements</b>", styles["Body"]))
        elements.append(Spacer(1, 4))

        table_data = [["Req", "Name", "Status", "Governing Document"]]
        for f in sorted(compliant, key=lambda x: x.requirement_id):
            req = req_map.get(f.requirement_id)
            name = (req.name if req else "")[:40]
            status = f.applicability_decision
            table_data.append([
                f.requirement_id,
                name,
                status,
                (f.governing_document or "")[:30],
            ])

        t = Table(table_data, colWidths=[0.6 * inch, 2.5 * inch, 1.3 * inch, 2.0 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.93, 0.96, 0.93)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.98, 0.99, 0.98)]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.Color(0.88, 0.88, 0.88)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(t)

    elements.append(PageBreak())
    return elements


def write_pdf_report(
    findings: list[Finding],
    packages: dict[str, ContractPackage],
    path: Path,
) -> Path:
    """Generate the PDF findings summary report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    req_map = requirement_map()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    elements = []

    # Cover page
    elements.extend(_build_cover_page(findings, packages, styles))

    # Group findings by package
    by_package: dict[str, list[Finding]] = {}
    for f in findings:
        by_package.setdefault(f.document_id, []).append(f)

    # Per-package sections
    for package_id in sorted(by_package.keys()):
        pkg_findings = by_package[package_id]
        package = packages.get(package_id)
        elements.extend(_build_package_section(
            package_id, pkg_findings, package, req_map, styles
        ))

    doc.build(elements)
    return path
