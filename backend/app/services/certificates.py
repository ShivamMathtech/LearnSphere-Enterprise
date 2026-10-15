import io
import secrets
from xml.sax.saxutils import escape
from fastapi import HTTPException
from sqlalchemy import select, update
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from app.core.config import settings
from app.db.base import now
from app.models import Enrollment, Course, User, Institution, Certificate, SystemSetting
from app.services.learning import eligibility
from app.services.common import audit, notify


def issue(db, p, enrollment):
    db.execute(update(Enrollment).where(Enrollment.id == enrollment.id).values(updated_at=now()))
    result = eligibility(db, enrollment)
    if not result["eligible"]:
        raise HTTPException(409, {"message": "Completion requirements are not satisfied", "remaining": result["remaining"]})
    existing = db.scalar(select(Certificate).where(Certificate.enrollment_id == enrollment.id, Certificate.revoked_at.is_(None)))
    if existing:
        return existing
    previous = db.scalar(select(Certificate).where(Certificate.enrollment_id == enrollment.id).order_by(Certificate.created_at.desc()))
    if previous and "certificates.manage" not in p.permissions:
        raise HTTPException(403, "Only an administrator can reissue a revoked certificate")
    user = db.get(User, enrollment.user_id)
    course = db.get(Course, enrollment.course_id)
    institution = db.get(Institution, enrollment.institution_id)
    configuration = db.scalar(
        select(SystemSetting).where(SystemSetting.institution_id == institution.id, SystemSetting.key == "certificate")
    )
    issuer = configuration.value.get("issuer", institution.name) if configuration else institution.name
    row = Certificate(
        institution_id=institution.id,
        enrollment_id=enrollment.id,
        code=secrets.token_urlsafe(24),
        student_name=user.name,
        course_title=course.title,
        issuer=issuer,
        supersedes_id=previous.id if previous else None,
    )
    enrollment.status, enrollment.completed_at = "completed", enrollment.completed_at or now()
    db.add(row)
    db.flush()
    audit(db, p, "certificates.issued", row)
    notify(db, institution.id, user.id, "Certificate earned", course.title)
    return row


def pdf(db, certificate):
    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle("LearnSphere completion certificate")
    c.setFillColor(colors.HexColor("#f5f8fc"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#0d9488"))
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60)
    institution = db.get(Institution, certificate.institution_id)
    setting = db.scalar(select(SystemSetting).where(SystemSetting.institution_id == institution.id, SystemSetting.key == "certificate"))
    config = setting.value if setting else {}

    def line(text, y, size, color="#10213a"):
        style = ParagraphStyle(
            "certificate", fontName="Helvetica", fontSize=size, leading=size * 1.4, alignment=1, textColor=colors.HexColor(color)
        )
        p = Paragraph(escape(text), style)
        _, h = p.wrap(width - 140, 100)
        p.drawOn(c, 70, y - h)

    line("LEARN SPHERE  /  ENTERPRISE", 535, 13, "#0d9488")
    line(config.get("heading", "Certificate of Completion"), 475, 32)
    line("This certifies that", 407, 13)
    line(certificate.student_name, 370, 28)
    line("has successfully completed", 308, 13)
    line(certificate.course_title, 274, 22)
    line(certificate.issuer, 210, 14)
    line("Completed " + certificate.created_at.strftime("%d %B %Y"), 177, 12)
    line(config.get("footer", "Issued upon completion of the configured learning requirements."), 145, 10)
    line("Verification code: " + certificate.code, 111, 10)
    line(settings().frontend_url + "/verify/" + certificate.code, 88, 9)
    if certificate.revoked_at:
        line("REVOKED", 55, 12, "#b91c1c")
    c.save()
    return buffer.getvalue()
