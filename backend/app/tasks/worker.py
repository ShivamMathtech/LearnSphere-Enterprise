"""Run once from Task Scheduler, cron, or a single worker container every minute."""

from typing import cast
from sqlalchemy.engine import CursorResult


from datetime import timedelta
from email.message import EmailMessage
import smtplib
from sqlalchemy import select, delete, update
from app.core.config import settings
from app.db.base import now
from app.db.session import SessionLocal
from app.models import EmailOutbox, Assignment, Enrollment, AuditEvent, Notification, PasswordResetToken, RateLimit, QuizAttempt
from app.security.crypto import cipher
from app.services.common import notify
from app.services.assessments import finish_attempt


def run_once():
    s = settings()
    with SessionLocal.begin() as db:
        for attempt in db.scalars(
            select(QuizAttempt).where(QuizAttempt.status == "in_progress", QuizAttempt.deadline <= now()).with_for_update(skip_locked=True)
        ):
            finish_attempt(db, attempt)
        for assignment in db.scalars(
            select(Assignment).where(Assignment.due_at >= now(), Assignment.due_at <= now() + timedelta(hours=24))
        ):
            for e in db.scalars(select(Enrollment).where(Enrollment.course_id == assignment.course_id, Enrollment.status == "active")):
                notify(db, e.institution_id, e.user_id, "Assignment due soon", assignment.title, f"due:{assignment.id}:{e.user_id}")
        # Recover interrupted sends after 15 minutes. SMTP is at-least-once; use Message-ID deduplication.
        db.execute(
            update(EmailOutbox)
            .where(EmailOutbox.status == "sending", EmailOutbox.updated_at < now() - timedelta(minutes=15))
            .values(status="pending")
        )
    if not s.smtp_host:
        return {"smtp": "unconfigured", "message": "No messages delivered"}
    sent = 0
    with SessionLocal() as db:
        ids = list(
            db.scalars(
                select(EmailOutbox.id)
                .where(
                    EmailOutbox.status.in_(["pending", "retry", "unconfigured"]),
                    EmailOutbox.next_attempt_at <= now(),
                    EmailOutbox.attempts < 5,
                )
                .order_by(EmailOutbox.created_at)
                .limit(50)
            )
        )
    for mail_id in ids:
        with SessionLocal.begin() as db:
            result = db.execute(
                update(EmailOutbox)
                .where(EmailOutbox.id == mail_id, EmailOutbox.status.in_(["pending", "retry", "unconfigured"]))
                .values(status="sending", attempts=EmailOutbox.attempts + 1)
            )
            if cast(CursorResult, result).rowcount != 1:
                continue
        try:
            with SessionLocal() as db:
                row = db.get(EmailOutbox, mail_id)
                if row is None:
                    continue
                msg = EmailMessage()
                msg["From"], msg["To"], msg["Subject"] = s.smtp_from, row.recipient, row.subject
                msg["Message-ID"] = f"<{row.id}@learnsphere.local>"
                msg.set_content(cipher().decrypt(row.encrypted_body.encode()).decode())
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                if s.smtp_starttls:
                    smtp.starttls()
                if s.smtp_user:
                    smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
            with SessionLocal.begin() as db:
                row = db.get(EmailOutbox, mail_id)
                if row is None:
                    continue
                row.status, row.encrypted_body = "sent", ""
                sent += 1
        except Exception as exc:
            with SessionLocal.begin() as db:
                row = db.get(EmailOutbox, mail_id)
                if row is None:
                    continue
                row.status = "failed" if row.attempts >= 5 else "retry"
                row.last_error = type(exc).__name__  # No addresses, credentials or message content in logs.
                row.next_attempt_at = now() + timedelta(minutes=2**row.attempts)
    return {"sent": sent}


def retention():
    s = settings()
    with SessionLocal.begin() as db:
        db.execute(delete(Notification).where(Notification.created_at < now() - timedelta(days=s.notification_retention_days)))
        db.execute(delete(AuditEvent).where(AuditEvent.created_at < now() - timedelta(days=s.audit_retention_days)))
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now() - timedelta(days=1)))
        db.execute(delete(RateLimit).where(RateLimit.resets_at < now()))
        db.execute(delete(EmailOutbox).where(EmailOutbox.created_at < now() - timedelta(days=30)))


if __name__ == "__main__":
    print(run_once())
