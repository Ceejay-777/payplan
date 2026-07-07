from payplan.utils.email_service import send_html_email
from django.conf import settings


def send_invitation_email(payer_email, cohort_name, resolution_link, amount, cohort_description='', expiry_minutes=None):
    if not payer_email:
        return

    if expiry_minutes is None:
        expiry_minutes = getattr(settings, 'PAYMENT_LINK_EXPIRY_MINUTES', 60)

    send_html_email(
        subject=f"You're invited to join {cohort_name}",
        template_path="emails/cohort_invitation.html",
        recipient=payer_email,
        context={
            "cohort_name": cohort_name,
            "cohort_description": cohort_description,
            "resolution_link": resolution_link,
            "amount": amount,
            "expiry_minutes": expiry_minutes,
        },
    )


def send_payer_joined_notification(organizer_email, organizer_name, cohort_name, payer_email):
    if not organizer_email:
        return

    send_html_email(
        subject=f"A payer has joined {cohort_name}",
        template_path="emails/payer_joined.html",
        recipient=organizer_email,
        context={
            "organizer_name": organizer_name,
            "cohort_name": cohort_name,
            "payer_email": payer_email,
        },
    )
