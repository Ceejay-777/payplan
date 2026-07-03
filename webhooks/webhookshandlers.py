from django.db import transaction
from plans.models import PayPlan
from plans.services import activate_plan, update_plan_for_charge
from transactions.services import record_transaction, schedule_dunning
from transactions.models import Transaction

import sentry_sdk

def handle_subscription_activated(data):
    try:
        sub_engine_id = data.get('subscription_id')
        plan = PayPlan.objects.select_for_update().get(engine_subscription_id=sub_engine_id)
        
        # Update plan with engine data
        activate_plan(plan)
        
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
    except Exception as e:
        sentry_sdk.logger.error(
            "Subscription activate failed: {error}",
            error=str(e),
        )

def handle_billing_success(data):
    try:
        with transaction.atomic():
            sub_engine_id = data.get('subscription_id')
            plan = PayPlan.objects.select_for_update().get(engine_subscription_id=sub_engine_id)
            
            # TODO: Check it transaction exists for the plan using an idempotency key. Probably get billing count from engine.
            
            # Record successful transaction or update existing one
            record_transaction(
                plan=plan,
                nomba_reference=data.get('reference'),
                amount=plan.amount,
                cycle_number=plan.billing_count + 1,
                status=Transaction.Status.CHARGE_SUCCESS
            )
            
            # Update plan for next billing cycle
            update_plan_for_charge(plan, data)
            
            sentry_sdk.logger.info(
                "Billing success handled for plan {plan_id} with engine subscription ID {sub_engine_id}",
                plan_id=plan.id,
                sub_engine_id=sub_engine_id,
                attributes={
                    "user_id": plan.creator.sqid,
                }
            )
            
    except PayPlan.DoesNotExist:
        sentry_sdk.logger.error(
            "Billing resolution failed: record not found for {sub_engine_id}",
            sub_engine_id=sub_engine_id,
        )
    except Exception as e:
        sentry_sdk.logger.error(
            "Billing resolution failed: {error}",
            error=str(e),
        )


def handle_billing_failed(data):
    try:
        with transaction.atomic():
            engine_id = data.get('subscription_id')
            plan = PayPlan.objects.get(engine_subscription_id=engine_id)
            
            # Record failed transaction
            transaction_record = record_transaction(
                plan=plan,
                nomba_reference=data.get('reference'),
                amount=plan.amount,
                cycle_number=plan.billing_count + 1,
                status=Transaction.Status.FAILED,
                failure_reason=data.get('reason')
            )
            
            # Schedule dunning
            schedule_dunning(transaction_record)
    except PayPlan.DoesNotExist:
        pass

def handle_dunning_exhausted(data):
    try:
        engine_id = data.get('subscription_id')
        plan = PayPlan.objects.get(engine_subscription_id=engine_id)
        plan.pause()
        # Notify payer (already handled in dunning service if internal, 
        # but if from engine, we do it here)
    except PayPlan.DoesNotExist:
        pass

def handle_subscription_cancelled(data):
    try:
        engine_id = data.get('subscription_id')
        plan = PayPlan.objects.get(engine_subscription_id=engine_id)
        plan.cancel()
    except PayPlan.DoesNotExist:
        pass
