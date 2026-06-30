import requests
from django.conf import settings

import datetime

# ENGINE_API_BASE_URL = "https://engine.payplan.app/api/v1"

def create_subscription(plan):
    """
    Registers the plan with the external subscription engine.
    Returns the sub_id.
    """
    # payload = {
    #     "plan_id": plan.sqid,
    #     "amount": str(plan.amount),
    #     "frequency": plan.frequency,
    #     "callback_url": "https://payplan.app/api/webhooks/engine"
    # }
    # try:
    #     response = requests.post(f"{ENGINE_API_BASE_URL}/subscriptions", json=payload, timeout=10)
    #     response.raise_for_status()
    #     return response.json()['id']
    # except Exception as e:
    #     raise Exception(f"Failed to register plan with engine: {e}")
    
    return {
        "subscription_id": "12345678",
        "next_billing_date": datetime.now(),
        # "amount": str(plan.amount),
        # "frequency": plan.frequency,
        # "callback_url": "https://payplan.app/api/webhooks/engine"
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
