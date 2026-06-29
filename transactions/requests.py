import requests
from django.conf import settings

# NOMBA_API_BASE_URL = "https://api.nomba.com/v1"

def call_nomba_charge_api(token, amount, reference):
    """
    Calls Nomba Charge API to bill a tokenized card.
    """
    raise NotImplementedError("Nomba Charge API not implemented")

def initiate_transfer(amount, account_number, bank_code):
    """
    Calls Nomba Transfers API to payout to receiver.
    """
    raise NotImplementedError("Nomba Transfers API not implemented")
