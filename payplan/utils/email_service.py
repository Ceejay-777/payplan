# payplan/utils/email_service.py
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def send_text_email(subject: str, body: str, recipient: str):
    """Send a plain text email to a single recipient."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[recipient],
        )
    except Exception as e:
        logger.error(f"Email send failed to {recipient}: {e}")
        raise Exception(f"Failed to send email to {recipient}") from e


def send_html_email(subject: str, template_path: str, recipient: str, context: dict):
    """
    Render a Django HTML template and send it to a single recipient.
    Always attaches a plain text fallback.
    """
    context.setdefault("base_url", settings.SERVICE_BASE_URL)

    html_content  = render_to_string(template_path, context)
    plain_content = render_to_string(
        template_path.replace(".html", "_plain.txt"), context
    ) if _plain_template_exists(template_path) else ""

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            to=[recipient],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception as e:
        logger.error(f"HTML email send failed to {recipient}: {e}")
        raise Exception(f"Failed to send email to {recipient}") from e


def send_bulk_email(subject: str, template_path: str, recipients: list, context: dict):
    """
    Send the same HTML email to multiple recipients individually.
    Each gets their own message — no recipient sees others' addresses.
    context: shared context applied to all emails.
    """
    context.setdefault("base_url", settings.SERVICE_BASE_URL)
    html_content = render_to_string(template_path, context)

    failed = []
    for recipient in recipients:
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body="",
                to=[recipient],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        except Exception as e:
            logger.error(f"Bulk email failed for {recipient}: {e}")
            failed.append(recipient)

    if failed:
        raise Exception(f"Email send failed for: {', '.join(failed)}")


def _plain_template_exists(template_path: str) -> bool:
    """Check if a plain text counterpart template exists."""
    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist
    try:
        get_template(template_path.replace(".html", "_plain.txt"))
        return True
    except TemplateDoesNotExist:
        return False