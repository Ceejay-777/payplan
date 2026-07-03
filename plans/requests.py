import requests
from django.conf import settings
import datetime

# Placeholder values, should be moved to settings/env
SUB_ENGINE_BASE_URL = "https://engine.payplan.app/api/developer"
SUB_ENGINE_API_KEY = "YOUR_API_KEY" 

def _get_headers():
    return {
        "Authorization": f"Bearer {SUB_ENGINE_API_KEY}",
        "Content-Type": "application/json"
    }

def create_customer(user):
    """
    Creates a customer in the sub-engine.
    """
    payload = {
        "email": user.email,
        "name": f"{user.first_name} {user.last_name}",
    }
    # response = requests.post(
    #     f"{SUB_ENGINE_BASE_URL}/customers/", 
    #     json=payload, 
    #     headers=_get_headers(), 
    #     timeout=10
    # )
    # response.raise_for_status()
    # return response.json()['id']
    return f"sub_engine_customer_id_placeholder-{user.sqid}"

def create_sub_engine_plan(plan):
    """
    Creates a plan in the sub-engine.
    """
    payload = {
        "name": plan.name,
        "amount": str(plan.amount),
        "currency": plan.currency,
        "interval": plan.interval,
        "interval_count": plan.interval_count,
    }
    return f"sub_engine_plan_id_placeholder-{plan.sqid}"

def create_subscription(customer_id, plan_id):
    """
    Registers the subscription with the external subscription engine.
    """
    
    payload = {
        "customer": customer_id,
        "plan": plan_id,
        "idempotency_key": f"subscription-{customer_id}-{plan_id}"
    }

    
def cancel_with_engine(engine_subscription_id):
    """
    Cancels the subscription in the engine.
    """
    raise NotImplementedError("Engine cancellation not implemented")

def resolve_bank_account(account_number, bank_code):
    """
    Resolves bank account name via Nomba.
    """
    # TODO: Call Resolve bank account
    
    return "John Doe Account"
