from django.db import transaction as db_transaction
from transactions.models import DunningAttempt
import sentry_sdk

from transactions.services import set_transaction_succeeded, handle_payout_failure

def handle_payout_success(data):
    payout_reference = data.get('id')
    try:
        with db_transaction.atomic():
            attempt = DunningAttempt.objects.select_for_update().get(payout_reference=payout_reference)
            transaction = attempt.transaction

            if attempt.status == DunningAttempt.Status.SUCCESS:
                sentry_sdk.logger.info(
                    "Payout success already handled for attempt {attempt_id}",
                    attempt_id=attempt.id,
                )
                return

            attempt.status = DunningAttempt.Status.SUCCESS
            attempt.save(update_fields=['status'])

            set_transaction_succeeded(transaction)

    except DunningAttempt.DoesNotExist:
        sentry_sdk.logger.error(
            "Payout success handling failed: no attempt found",
            attributes={"payout_reference": payout_reference},
        )
        raise


def handle_payout_refund(data):
    payout_reference = data.get('id')
    try:
        with db_transaction.atomic():
            attempt = DunningAttempt.objects.select_for_update().get(payout_reference=payout_reference)

            if attempt.status in (DunningAttempt.Status.SUCCESS, DunningAttempt.Status.FAILED):
                sentry_sdk.logger.info(
                    "Payout refund already handled for attempt {attempt_id}",
                    attempt_id=attempt.id,
                )
                return

            reason = data.get('reason', 'Unknown reason')
            handle_payout_failure(attempt, reason)

    except DunningAttempt.DoesNotExist:
        sentry_sdk.logger.error(
            "Payout refund handling failed: no attempt found",
            attributes={"payout_reference": payout_reference},
        )
        raise