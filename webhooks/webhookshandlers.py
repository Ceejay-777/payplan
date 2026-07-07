from django.db import transaction
from plans.models import PayPlan
from plans.services import activate_plan, update_plan_for_charge
from transactions.services import record_transaction
from transactions.models import Transaction, TransactionEvent
from transactions.services import create_and_run_first_payout_attempt

import sentry_sdk

def handle_subscription_activated(data):
    sub_engine_id = data.get('subscription_id')
    try:
        with transaction.atomic():
            plan = PayPlan.objects.select_for_update().get(engine_subscription_id=sub_engine_id)
            
            if plan.status == PayPlan.Status.ACTIVE:
                sentry_sdk.logger.info(
                    "Subscription activated already handled for plan {plan_id}",
                    plan_id=plan.id,
                )
                return
            
            # Update plan with engine data
            activate_plan(plan, data)
        
        sentry_sdk.logger.info(
            "Subscription activated for plan {plan_id} with engine subscription ID {sub_engine_id}",
            plan_id=plan.id,
            sub_engine_id=sub_engine_id,
            attributes={
                "user_id": plan.creator.sqid,
            }
        )
        
    except PayPlan.DoesNotExist:
        sentry_sdk.logger.error(
            "Subscription activate failed: record not found for {sub_engine_id}",
            sub_engine_id=sub_engine_id,
        )
        raise
    except Exception as e:
        sentry_sdk.logger.error(
            "Subscription activate failed: {error}",
            error=str(e),
        )
        raise

def handle_billing_success(data):
    sub_engine_id = data.get('subscription_id')

    try:
        with transaction.atomic():
            plan = PayPlan.objects.select_for_update().get(engine_subscription_id=sub_engine_id)

            charge_reference = data.get('reference')

            existing_transaction = Transaction.objects.filter(
                charge_reference=charge_reference,
            ).first()

            if existing_transaction:
                sentry_sdk.set_tag("transaction_id", existing_transaction.sqid)
                sentry_sdk.logger.info(
                    "Billing success already handled for charge reference {charge_reference}",
                    charge_reference=charge_reference,
                )
                return

            cycle_number = plan.billing_count + 1

            transaction_record = record_transaction(
                plan=plan,
                charge_reference=charge_reference,
                amount=plan.amount,
                cycle_number=cycle_number,
                status=Transaction.Status.CHARGE_SUCCESS,
                event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED
            )

            sentry_sdk.set_tag("transaction_id", transaction_record.sqid)

            update_plan_for_charge(plan, data)

            sentry_sdk.logger.info(
                "Billing success handled for plan {plan_id} with engine subscription ID {sub_engine_id}",
                plan_id=plan.id,
                sub_engine_id=sub_engine_id,
                attributes={
                    "user_id": plan.creator.sqid,
                }
            )

            create_and_run_first_payout_attempt(transaction_record)

    except PayPlan.DoesNotExist:
        sentry_sdk.logger.error(
            "Billing resolution failed: record not found for {sub_engine_id}",
            sub_engine_id=sub_engine_id,
        )
        raise
    except Exception as e:
        sentry_sdk.logger.error(
            "Billing resolution failed: {error}",
            error=str(e),
        )
        raise


# def handle_billing_failed(data):
#     try:
#         with transaction.atomic():
#             sub_engine_id = data.get('subscription_id')
#             plan = PayPlan.objects.select_for_update().get(engine_subscription_id=sub_engine_id)
            
#             # Record failed transaction
#             transaction_record = record_transaction(
#                 plan=plan,
#                 charge_reference=data.get('reference'),
#                 amount=plan.amount,
#                 cycle_number=plan.billing_count + 1,
#                 status=Transaction.Status.FAILED,
#                 failure_reason=data.get('reason')
#             )
            
#             # Schedule dunning
#             schedule_dunning(transaction_record)
#     except PayPlan.DoesNotExist:
#         pass

# def handle_dunning_exhausted(data):
#     try:
#         engine_id = data.get('subscription_id')
#         plan = PayPlan.objects.get(engine_subscription_id=engine_id)
#         plan.pause()
#         # Notify payer (already handled in dunning service if internal, 
#         # but if from engine, we do it here)
#     except PayPlan.DoesNotExist:
#         pass

# def handle_subscription_cancelled(data):
#     try:
#         engine_id = data.get('subscription_id')
#         plan = PayPlan.objects.get(engine_subscription_id=engine_id)
#         plan.cancel()
#     except PayPlan.DoesNotExist:
#         pass
