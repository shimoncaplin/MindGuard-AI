# MindGuard AI - Executive PDF Generator Module
# Drop this file into your project and import the function.
# Generated for Shimon.

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

def generate_board_report_pdf(output_path, workspace_name, analysis, verdict, risks, recommendations):
    doc = SimpleDocTemplate(output_path)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("MindGuard AI Board Report", styles["Title"]))
    story.append(Paragraph(f"Workspace: {workspace_name}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.utcnow()}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    story.append(Paragraph(str(analysis.get("executive_summary", "")), styles["BodyText"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Key Metrics", styles["Heading1"]))
    story.append(Paragraph(f"AI Health: {analysis.get('health', 0)}/100", styles["BodyText"]))
    story.append(Paragraph(f"Average Score: {analysis.get('avg_score', 0)}", styles["BodyText"]))
    story.append(Paragraph(f"Deployment Verdict: {verdict}", styles["BodyText"]))

    story.append(PageBreak())
    story.append(Paragraph("Top Risks", styles["Heading1"]))
    for r in risks:
        story.append(Paragraph(f"• {r}", styles["BodyText"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Recommendations", styles["Heading1"]))
    for rec in recommendations:
        story.append(Paragraph(f"• {rec}", styles["BodyText"]))

    doc.build(story)
    return output_path
