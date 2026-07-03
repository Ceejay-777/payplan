from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import timedelta
from django_q.tasks import schedule
from .models import Transaction, DunningAttempt, TransactionEvent
from plans.models import PayPlan
# from payplan.utils.email_service import send_email_notification

def _log_transaction_event(transaction, event_type, previous_status, new_status, metadata=None):
    event = TransactionEvent.objects.create(
        transaction=transaction,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {}
    )
    
    return event

def record_transaction(plan, nomba_reference, amount, cycle_number, status, event_type, failure_reason=None):
    
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
                nomba_reference= nomba_reference,
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

def schedule_dunning(transaction):
    """
    Schedules 3 dunning attempts: 1 day, 3 days, 7 days after failure.
    """
    schedules = [1, 3, 7]
    attempts = []
    for i, days in enumerate(schedules, 1):
        scheduled_at = timezone.now() + timedelta(days=days)
        attempt = DunningAttempt.objects.create(
            transaction=transaction,
            attempt_number=i,
            scheduled_at=scheduled_at,
            status=DunningAttempt.Status.SCHEDULED
        )
        # Schedule the background task (django-q2)
        schedule(
            'transactions.tasks.run_dunning_attempt',
            attempt.id,
            next_run=scheduled_at
        )
        attempts.append(attempt)
    return attempts

def handle_dunning_failure(attempt):
    """
    Called when a dunning attempt fails.
    If it was the last attempt, pause the plan.
    """
    if attempt.attempt_number == 3:
        plan = attempt.transaction.plan
        plan.pause()
        # send_email_notification(
        #     "Payment Failed - Plan Paused",
        #     f"All retry attempts for plan {plan.title} have failed. Your plan has been paused.",
        #     [plan.payer_email]
        # )
