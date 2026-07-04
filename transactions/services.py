from django.db import transaction as db_transaction
from django_q.tasks import schedule
from django.utils import timezone

from datetime import timedelta
import sentry_sdk

from .models import Transaction, DunningAttempt, TransactionEvent
from .requests import transfer

from transactions.exceptions import NombaConnectionError, NombaTransferRejected
from transactions.models import Transaction, TransactionEvent, DunningAttempt

PAYOUT_SCHEDULES = [1, 4, 12] #NOTE: In hours

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

def create_and_run_first_payout_attempt(transaction):
    #NOTE: Attempt number 0 = original attempt, not a retry
    attempt = DunningAttempt.objects.create(
        transaction=transaction,
        attempt_number=0,
        scheduled_at=timezone.now(),
        status=DunningAttempt.Status.SCHEDULED
    )
    initiate_payout(attempt)

def initiate_payout(attempt):
    """
    Initiates a payout for a given transaction.
    """
    transaction = attempt.transaction
    plan = transaction.plan
    merchant_tx_ref=f"PAYOUT_{transaction.sqid}_ATTEMPT_{attempt.attempt_number}"
    
    try:
        
        payout_data = transfer(
            amount=transaction.amount,
            account_number=plan.receiver_account_number,
            account_name=plan.receiver_account_name,
            bank_code=plan.receiver_bank_code,
            merchant_tx_ref=merchant_tx_ref,
            sender_name="PayPlan",
            narration=f"Payout for {plan.title} cycle {transaction.billing_cycle_number}"
        )
        
        with db_transaction.atomic():
            #TODO: Get actual payout reference
            attempt.payout_reference = payout_data.get('id')
            attempt.status = DunningAttempt.Status.AWAITING_CONFIRMATION
            attempt.save(update_fields=['merchant_tx_ref', 'payout_reference', 'status'])
            
            previous_status = transaction.status
            transaction.status = Transaction.Status.PAYOUT_PENDING
            transaction.save(update_fields=['status'])
            
            _log_transaction_event(
                transaction=transaction,
                event_type=TransactionEvent.EventTypes.PAYOUT_INITIATED,
                previous_status=previous_status,
                new_status=Transaction.Status.PAYOUT_PENDING,
                metadata={"attempt_number": attempt.attempt_number, "merchant_tx_ref": merchant_tx_ref}
            )
        
    except NombaTransferRejected as e:
        sentry_sdk.logger.error(f"Payout rejected for transaction {transaction.sqid}: {e}")
        handle_payout_failure(transaction, str(e))
        raise

    except NombaConnectionError as e:
        sentry_sdk.logger.warning(f"Payout outcome unknown for transaction {transaction.sqid}: {e}")
        raise
        
    except Exception as e:
        sentry_sdk.logger.error(
            "Unexpected error during payout initiation - treating as unknown outcome",
            attributes={"transaction_id": transaction.sqid, "attempt_number": attempt.attempt_number, "error": str(e)},
        )
        raise

def handle_payout_failure(transaction, reason, attempt):
    """
    Handles payout failure, schedules dunning/retry.
    """
    with db_transaction.atomic():
        attempt.status = DunningAttempt.Status.FAILED
        attempt.failure_reason = reason
        attempt.save(update_fields=['status', 'failure_reason'])
        
        previous_status = transaction.status
        transaction.status = Transaction.Status.PAYOUT_FAILED
        transaction.save(update_fields=['status'])
        
        _log_transaction_event(
            transaction=transaction,
            event_type=TransactionEvent.EventTypes.PAYOUT_FAILED,
            previous_status=previous_status,
            new_status=Transaction.Status.PAYOUT_FAILED
        )
        
        next_attempt_number = attempt.attempt_number + 1
        if next_attempt_number > len(PAYOUT_SCHEDULES):
            pause_plan(transaction.plan)
            return 
    
    schedule_next_payout_attempt(attempt)

def schedule_next_payout_attempt(failed_attempt):
    transaction = failed_attempt.transaction
    
    next_attempt_number = failed_attempt.attempt_number + 1
    
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

def pause_plan(plan):
    plan.pause()
    
    #TODO: Notify user about plan pause due to payout failures 

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