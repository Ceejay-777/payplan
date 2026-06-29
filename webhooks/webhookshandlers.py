from django.db import transaction
from plans.models import PayPlan
from transactions.services import record_transaction, schedule_dunning
from transactions.models import Transaction

def handle_billing_success(data):
    try:
        with transaction.atomic():
            engine_id = data.get('subscription_id')
            plan = PayPlan.objects.get(engine_subscription_id=engine_id)
            
            # Record success transaction
            record_transaction(
                plan=plan,
                nomba_reference=data.get('reference'),
                amount=plan.amount,
                cycle_number=plan.billing_count + 1,
                status=Transaction.Status.SUCCESS
            )
            
            # Update plan
            plan.billing_count += 1
            # In a real app, update next_billing_date from engine data or calculate
            if plan.max_billing_cycles and plan.billing_count >= plan.max_billing_cycles:
                plan.complete()
            else:
                # plan.next_billing_date = ...
                pass
            plan.save()
    except PayPlan.DoesNotExist:
        pass # Log error

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
