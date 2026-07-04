from django.db import transaction as db_transaction
from transactions.models import Transaction, TransactionEvent
import sentry_sdk

from transactions.services import set_transaction_succeeded

def handle_payout_success(data):
    try:
        with db_transaction.atomic():
            # TODO: Use correct reference
            payout_reference = data.get('id')
            transaction = Transaction.objects.select_for_update().get(payout_reference=payout_reference)
            
            if transaction.status == Transaction.Status.PAYOUT_SUCCESS:
                sentry_sdk.logger.info(
                    "Payout success already handled for transaction {transaction_id} with payout reference {payout_reference}",
                    transaction_id=transaction.id,
                    payout_reference=payout_reference
                )
                return
            
            set_transaction_succeeded(transaction)
        
    except Transaction.DoesNotExist:
        sentry_sdk.logger.error("Payout status update failed: transaction not found", extra={"payout_reference": payout_reference})
        raise
    except Exception as e:
        sentry_sdk.logger.error(f"Payout status update failed: {e}", extra={"payout_reference": payout_reference})
        raise