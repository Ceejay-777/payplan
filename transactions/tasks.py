from .models import Transaction, DunningAttempt
from .services import record_transaction, handle_payout_retry_failure, initiate_payout
from django.utils import timezone
import sentry_sdk

def run_payout_retry(dunning_attempt_id):
    """
    Background task to retry a failed payout.
    """
    try:
        attempt = DunningAttempt.objects.get(sqid=dunning_attempt_id)
        transaction = attempt.transaction
        
        attempt.attempted_at = timezone.now()
        
        initiate_payout(transaction.plan, transaction)
        
        #TODO: If success, mark attempt as success - Do this in webhook?
        attempt.status = DunningAttempt.Status.SUCCESS
        attempt.save(update_fields=['status', 'attempted_at'])
        
        sentry_sdk.logger.info(f"Payout retry successful for transaction {transaction.sqid} on attempt {attempt.attempt_number}")
        
    except DunningAttempt.DoesNotExist:
        sentry_sdk.logger.error("Payout retry failed: dunning attempt not found", extra={"dunning_attempt_id": dunning_attempt_id})
        raise
    
    except Exception as e:
        attempt.status = DunningAttempt.Status.FAILED
        attempt.failure_reason = str(e)
        attempt.save(update_fields=['status', 'failure_reason'])
        
        handle_payout_retry_failure(attempt)
        
        sentry_sdk.logger.error(f"Payout retry failed: {e}", extra={"dunning_attempt_id": dunning_attempt_id})
