from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import tempfile

def generate_client_report_pdf(workspace_name, analysis):
    pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name

    doc = SimpleDocTemplate(pdf_path)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("MindGuard AI Client Share Report", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Workspace: {workspace_name}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.utcnow()}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    story.append(
        Paragraph(
            str(analysis.get("executive_summary", "No executive summary available.")),
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))
    story.append(Paragraph("Metrics", styles["Heading1"]))
    story.append(Paragraph(f"AI Health: {analysis.get('health', 0)}/100", styles["BodyText"]))
    story.append(Paragraph(f"Average Score: {analysis.get('avg_score', 0)}", styles["BodyText"]))
    story.append(Paragraph(f"Critical Issues: {analysis.get('bad_count', 0)}", styles["BodyText"]))
    story.append(Paragraph(f"Weak Responses: {analysis.get('weak_count', 0)}", styles["BodyText"]))

    doc.build(story)
    return pdf_path
