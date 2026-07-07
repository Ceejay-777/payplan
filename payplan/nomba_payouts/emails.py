from datetime import datetime
from decimal import Decimal

from django.conf import settings

from payplan.utils.email_service import send_html_email


def _format_amount(amount):
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return f"{amount:,.2f}"


def _brand_context():
    """Context the brand chrome (emails/base.html) needs. The base template
    uses `frontend_url` and `year`; the email_service helper only injects
    `base_url`, so we set them here explicitly to keep this module
    self-contained and not depend on the (currently inconsistent) defaults
    of the shared email helper.
    """
    return {
        "frontend_url": getattr(settings, "BASE_URL", "").rstrip("/"),
        "year": datetime.now().year,
    }


def send_payout_success_email(*, plan, transaction, attempt):
    """Notify the plan creator that a payout to the receiver succeeded."""
    send_html_email(
        subject=f"PayPlan payout sent: {plan.title}",
        template_path="payplan/nomba_payouts/payout_success.html",
        recipient=plan.creator.email,
        context={
            "plan_title": plan.title,
            "amount": _format_amount(transaction.amount),
            "currency": transaction.currency,
            "cycle_number": transaction.billing_cycle_number,
            "payout_reference": attempt.payout_reference or "",
            **_brand_context(),
        },
    )


def send_payout_failure_email(*, plan, transaction, attempt, reason):
    """Notify the plan creator that a payout to the receiver failed permanently
    (after retries are exhausted). For transient failures mid-retry schedule
    we stay silent — the plan will be paused and the creator should not be
    paged on every retry.
    """
    send_html_email(
        subject=f"PayPlan payout failed: {plan.title}",
        template_path="payplan/nomba_payouts/payout_failure.html",
        recipient=plan.creator.email,
        context={
            "plan_title": plan.title,
            "amount": _format_amount(transaction.amount),
            "currency": transaction.currency,
            "cycle_number": transaction.billing_cycle_number,
            "payout_reference": attempt.payout_reference or "",
            "failure_reason": reason or "Unknown reason",
            **_brand_context(),
        },
    )
