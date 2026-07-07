from payplan.nomba_payouts.client import lookup_bank_account
from payplan.requests import sub_engine_request

def resolve_bank_account(account_number, bank_code):
    """
    Resolves bank account name via Nomba.
    """
    return lookup_bank_account(account_number, bank_code)

def create_customer(user):
    payload = {
        "email": user.email,
        "name": f"{user.first_name} {user.last_name}",
    }
    
    return f"sub_engine_customer_id_placeholder-{user.sqid}"

def create_sub_engine_plan(plan):
    payload = {
        "name": plan.name,
        "amount": str(plan.amount),
        "currency": plan.currency,
        "interval": plan.interval,
        "interval_count": plan.interval_count,
    }
    
    return f"sub_engine_plan_id_placeholder-{plan.sqid}"

def create_subscription(customer_id, plan_id):
    payload = {
        "customer": customer_id,
        "plan": plan_id,
        "idempotency_key": f"subscription-{customer_id}-{plan_id}"
    }
    
    return {
        "id": f"sub_engine_subscription_id_placeholder-{customer_id}-{plan_id}",
        "order_referece": f"subscription-{customer_id}-{plan_id}",
        "checkout_link": f"https://subengine.example.com/checkout/{customer_id}/{plan_id}",
    }

    
def cancel_with_engine(engine_subscription_id):
    """
    Cancels the subscription in the engine.
    """
    raise NotImplementedError("Engine cancellation not implemented")


