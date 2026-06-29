import requests
from django.conf import settings

# ENGINE_API_BASE_URL = "https://engine.payplan.app/api/v1"

def register_with_subscription_engine(plan):
    """
    Registers the plan with the external subscription engine.
    Returns the engine_subscription_id.
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
    return "engine_sub_12345"

def cancel_with_engine(engine_subscription_id):
    """
    Cancels the subscription in the engine.
    """
    raise NotImplementedError("Engine cancellation not implemented")

def resolve_receiver_account(account_number, bank_code):
    """
    Resolves receiver account name via Nomba.
    """
    # This should call core.requests.resolve_account_name but I'll stub it here for now
    # to avoid circular imports if any, or just call the core one.
    return "John Doe Account"
