import requests
from django.conf import settings
import sentry_sdk

def nomba_request(method, endpoint, payload=None, timeout=10):
    """
    Helper function to make requests to the Nomba API.
    """
    url = f"https://api.nomba.com/v2/{endpoint}/"
    
    headers = {
        'Authorization': f'Bearer {settings.NOMBA_API_KEY}',
        'Content-Type': 'application/json',
        'accountId': settings.NOMBA_ACCOUNT_ID
    }
    
    try:
        response = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
        return response
    
    except requests.exceptions.RequestException as e:
        sentry_sdk.logger.error("Nomba request failed", attributes={"error": str(e), "endpoint": endpoint, "payload": payload})
        raise 
    
def sub_engine_request(method, endpoint, payload=None, timeout=10):
    """
    Helper function to make requests to the Sub-Engine API.
    """
    url = f"https://<your-domain>/api/developer/{endpoint}/"
    
    headers = {
        'Authorization': f'Bearer {settings.SUB_ENGINE_API_KEY}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
        return response
    
    except requests.exceptions.RequestException as e:
        sentry_sdk.logger.error("Sub-Engine request failed", attributes={"error": str(e), "endpoint": endpoint, "payload": payload})
        raise 