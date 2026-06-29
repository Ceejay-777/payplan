from .models import Transaction, DunningAttempt
from .services import record_transaction, handle_dunning_failure
from django.utils import timezone
import requests

def run_dunning_attempt(dunning_attempt_id):
    """
    Background task to run a dunning attempt.
    """
    try:
        attempt = DunningAttempt.objects.get(id=dunning_attempt_id)
    except DunningAttempt.DoesNotExist:
        return

    plan = attempt.transaction.plan
    payer_card = plan.payer_card
    
    if not payer_card:
        attempt.status = DunningAttempt.Status.FAILED
        attempt.failure_reason = "No payer card attached to plan"
        attempt.save()
        handle_dunning_failure(attempt)
        return

    # Call Nomba Charge API (stubbed logic)
    # try:
    #     response = call_nomba_charge_api(payer_card.nomba_token, plan.amount)
    #     if response.success:
    #         attempt.status = DunningAttempt.Status.SUCCESS
    #         attempt.save()
    #         # Record new successful transaction
    #         record_transaction(plan, response.reference, plan.amount, attempt.transaction.billing_cycle_number, Transaction.Status.SUCCESS)
    #         # Update plan
    #         plan.billing_count += 1
    #         plan.save()
    #     else:
    #         attempt.status = DunningAttempt.Status.FAILED
    #         attempt.failure_reason = response.error
    #         attempt.save()
    #         handle_dunning_failure(attempt)
    # except Exception as e:
    #     attempt.status = DunningAttempt.Status.FAILED
    #     attempt.failure_reason = str(e)
    #     attempt.save()
    #     handle_dunning_failure(attempt)

    # Simplified stub for success/failure
    attempt.attempted_at = timezone.now()
    attempt.status = DunningAttempt.Status.FAILED # Assume it still fails for now
    attempt.save()
    handle_dunning_failure(attempt)
