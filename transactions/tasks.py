from .models import DunningAttempt
from .services import initiate_payout
from django.utils import timezone
import sentry_sdk

def run_payout_retry(dunning_attempt_id):
    try:
        attempt = DunningAttempt.objects.get(sqid=dunning_attempt_id)
        
    except DunningAttempt.DoesNotExist:
        sentry_sdk.logger.error(
            "Payout retry failed: dunning attempt not found",
            attributes={"dunning_attempt_id": dunning_attempt_id},
        )
        raise  
    
    attempt.attempted_at = timezone.now()
    attempt.status = DunningAttempt.Status.AWAITING_CONFIRMATION
    attempt.save(update_fields=['status', 'attempted_at'])
    
    transaction = attempt.transaction
    initiate_payout(attempt)
    
    sentry_sdk.logger.info(
        "Payout retry accepted by Nomba, awaiting webhook confirmation",
        attributes={"transaction_id": transaction.sqid, "attempt_number": attempt.attempt_number},
    )
