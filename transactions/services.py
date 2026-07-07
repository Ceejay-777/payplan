from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Transaction, TransactionEvent


def _log_transaction_event(transaction, event_type, previous_status, new_status, metadata=None):
    event = TransactionEvent.objects.create(
        transaction=transaction,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {}
    )

    return event

def record_transaction(plan, charge_reference, amount, cycle_number, status, event_type, failure_reason=None):

    with db_transaction.atomic():
        transaction = Transaction.objects.select_for_update().filter(plan=plan, billing_cycle_number=cycle_number).first()

        if transaction:
            previous_status = transaction.status

            transaction.status = status
            transaction.failure_reason = failure_reason
            transaction.save(update_fields=["status", "failure_reason"])
        else:
            previous_status = None

            transaction = Transaction.objects.create(
                plan=plan,
                billing_cycle_number=cycle_number,
                charge_reference= charge_reference,
                amount= amount,
                status= status,
                failure_reason= failure_reason,
                charged_at= timezone.now() if status == Transaction.Status.CHARGE_SUCCESS else None
            )

        _log_transaction_event(
            transaction=transaction,
            event_type=event_type,
            previous_status = previous_status,
            new_status=status,
        )

    return transaction
