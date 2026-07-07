from django.db import transaction as db_transaction
from transactions.models import DunningAttempt
import sentry_sdk

from transactions.services import set_transaction_succeeded, handle_payout_failure

def handle_payout_success(data):
    print("Handling payout success")
    payout_reference = data.get('transaction').get('transactionId')
    sentry_sdk.set_tag("payout_reference", payout_reference)
    try:
        with db_transaction.atomic():
            attempt = DunningAttempt.objects.select_for_update().get(payout_reference=payout_reference)
            sentry_sdk.set_tag("transaction_id", attempt.transaction.sqid)
            sentry_sdk.set_tag("attempt_id", attempt.sqid)
            sentry_sdk.set_tag("attempt_number", attempt.attempt_number)
            transaction = attempt.transaction

            if attempt.status == DunningAttempt.Status.SUCCESS:
                sentry_sdk.logger.info(
                    "Payout success already handled for attempt {attempt_id}",
                    attempt_id=attempt.id,
                )
                return

            attempt.status = DunningAttempt.Status.SUCCESS
            attempt.save(update_fields=['status'])

            set_transaction_succeeded(transaction, attempt=attempt)

    except DunningAttempt.DoesNotExist:
        sentry_sdk.logger.error(
            "Payout success handling failed: no attempt found",
            attributes={"payout_reference": payout_reference},
        )
        raise


def handle_payout_refund(data):
    payout_reference = data.get('id')
    sentry_sdk.set_tag("payout_reference", payout_reference)
    try:
        with db_transaction.atomic():
            attempt = DunningAttempt.objects.select_for_update().get(payout_reference=payout_reference)
            sentry_sdk.set_tag("transaction_id", attempt.transaction.sqid)
            sentry_sdk.set_tag("attempt_id", attempt.sqid)
            sentry_sdk.set_tag("attempt_number", attempt.attempt_number)
            
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