import requests
from django.conf import settings

# NOMBA_API_BASE_URL = "https://api.nomba.com/v1"
# NOMBA_SECRET_KEY = settings.NOMBA_SECRET_KEY

def initiate_checkout(email, amount=None):
    """
    Initiates Nomba Checkout to tokenize a card.
    Returns a checkout URL or session for the frontend.
    """
    raise NotImplementedError("Nomba Checkout integration not yet implemented")

def resolve_account_name(account_number, bank_code):
    """
    Resolves account name via Nomba Account Discovery API.
    Returns the account name.
    """
    raise NotImplementedError("Nomba Account Resolution not yet implemented")
