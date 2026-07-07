from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from payplan.utils.generate import generate_unique_token
from .email_notifications import send_invitation_email
from plans.models import PayPlan
from plans.services import _log_plan_event, PayPlanEvent
from .models import CohortMembership

BASE_URL = settings.BASE_URL
PAYMENT_LINK_EXPIRY_MINUTES = settings.PAYMENT_LINK_EXPIRY_MINUTES


def create_cohort_plan(cohort, payer_data):
    payment_link_token = generate_unique_token()

    plan = PayPlan.objects.create(
        title=payer_data.get('title', payer_data.get('name', '')),
        payer_email=payer_data.get('email', ''),
        description=cohort.description,
        amount=payer_data['amount'],
        currency='NGN',
        frequency=cohort.frequency,
        status=PayPlan.Status.DRAFT,
        receiver_account_name=cohort.receiver_account_name,
        receiver_account_number=cohort.receiver_account_number,
        receiver_bank_code=cohort.receiver_bank_code,
        payment_link_token=payment_link_token,
        payment_link_expires_at=timezone.now() + timedelta(minutes=PAYMENT_LINK_EXPIRY_MINUTES),
        cohort_id=cohort.sqid,
    )
    plan.refresh_from_db()

    _log_plan_event(
        plan=plan,
        event_type=PayPlanEvent.EventTypes.PLAN_CREATED,
        new_status=plan.status,
        metadata={"cohort_id": cohort.sqid},
    )

    membership = CohortMembership.objects.create(
        cohort=cohort,
        plan=plan,
        amount=payer_data['amount'],
        status=CohortMembership.Status.INVITED,
        metadata={
            **payer_data.get('metadata', {}),
            'proration_mode': cohort.proration_mode,
            'cohort_start_date': cohort.start_date.isoformat(),
        },
    )

    resolution_link = f"{BASE_URL}?p={plan.sqid}&plt={payment_link_token}&c={cohort.sqid}"

    send_invitation_email(
        payer_email=payer_data.get('email'),
        cohort_name=cohort.name,
        resolution_link=resolution_link,
        amount=payer_data['amount'],
        cohort_description=cohort.description,
    )

    return plan, membership, resolution_link
