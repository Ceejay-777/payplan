from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import timedelta
from django_q.tasks import schedule
from .models import Transaction, DunningAttempt, TransactionEvent
from plans.models import PayPlan
from .requests import transfer
from transactions.models import Transaction, TransactionEvent, DunningAttempt
from django_q.tasks import schedule
from django.utils import timezone
from datetime import timedelta
import sentry_sdk

PAYOUT_SCHEDULES = [1, 4, 12] # hours

def _log_transaction_event(transaction, event_type, previous_status, new_status, metadata=None):
    event = TransactionEvent.objects.create(
        transaction=transaction,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {}
    )
    
    return event

def initiate_payout(plan, transaction):
    """
    Initiates a payout for a given transaction.
    """
    try:
        last_attempt = DunningAttempt.objects.filter(transaction=transaction).order_by('-attempt_number').first()
        
        if last_attempt and last_attempt.status == DunningAttempt.Status.SUCCESS:
            return
        
        attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1
        
        # Payout logic
        payout_data = transfer(
            amount=transaction.amount,
            account_number=plan.receiver_account_number,
            account_name=plan.receiver_account_name,
            bank_code=plan.receiver_bank_code,
            merchant_tx_ref=f"PAYOUT_{transaction.sqid}_ATTEMPT_{attempt_number}",
            sender_name="PayPlan",
            narration=f"Payout for {plan.title} cycle {transaction.billing_cycle_number}"
        )
        
        # Update transaction status
        previous_status = transaction.status
        transaction.status = Transaction.Status.PAYOUT_PENDING
        transaction.payout_reference = payout_data.get('id')
        transaction.save(update_fields=['status', 'payout_reference'])
        
        _log_transaction_event(
            transaction=transaction,
            event_type=TransactionEvent.EventTypes.PAYOUT_INITIATED,
            previous_status=previous_status,
            new_status=Transaction.Status.PAYOUT_PENDING
        )
        
    except Exception as e:
        sentry_sdk.logger.error(f"Payout initiation failed for transaction {transaction.sqid}: {e}")
        handle_payout_failure(transaction, str(e))
        raise

def handle_payout_failure(transaction, reason):
    """
    Handles payout failure, schedules dunning/retry.
    """
    previous_status = transaction.status
    transaction.status = Transaction.Status.PAYOUT_FAILED
    transaction.payout_failure_reason = reason
    transaction.save(update_fields=['status', 'payout_failure_reason'])
    
    _log_transaction_event(
        transaction=transaction,
        event_type=TransactionEvent.EventTypes.PAYOUT_FAILED,
        previous_status=previous_status,
        new_status=Transaction.Status.PAYOUT_FAILED
    )
    
    # Notify receiver
    # from notifications.services import send_payout_failed_email
    # send_payout_failed_email(transaction.plan.creator, transaction)
    
    #TODO: If the payment dunning has not been scheduled before only
    schedule_payout_dunning(transaction)

def schedule_payout_dunning(transaction):
    last_attempt = DunningAttempt.objects.filter(transaction=transaction).order_by('-attempt_number').first()
    
    if last_attempt and last_attempt.status == DunningAttempt.Status.SUCCESS:
        return
    
    next_attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1
    hours = PAYOUT_SCHEDULES[next_attempt_number - 1]
    
    scheduled_at = timezone.now() + timedelta(hours=hours)
    attempt = DunningAttempt.objects.create(
        transaction=transaction,
        attempt_number=next_attempt_number,
        scheduled_at=scheduled_at,
        status=DunningAttempt.Status.SCHEDULED
    )
    
    attempt.refresh_from_db()
    
    schedule(
        'transactions.tasks.run_payout_retry',
        attempt.sqid,
        next_run=scheduled_at
    )

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

def handle_payout_retry_failure(attempt):
    """
    Called when a dunning attempt fails.
    If it was the last attempt, pause the plan.
    """
    transaction = attempt.transaction
    
    if attempt.attempt_number == transaction.max_payout_attempts:
        plan = attempt.transaction.plan
        plan.pause()
        
        # send_email_notification(
        #     "Payment Failed - Plan Paused",
        #     f"All retry attempts for plan {plan.title} have failed. Your plan has been paused.",
        #     [plan.payer_email]
        # )
        
def set_transaction_succeeded(transaction):
    
    previous_status = transaction.status
    transaction.status = Transaction.Status.PAYOUT_SUCCESS
    event_type = TransactionEvent.EventTypes.PAYOUT_SUCCEEDED
    
    transaction.save(update_fields=['status'])
    
    _log_transaction_event(
            transaction=transaction,
            event_type=event_type,
            previous_status=previous_status,
            new_status=Transaction.Status.PAYOUT_SUCCESS
        )
    
    # TODO: Send notification and email