import requests
from django.conf import settings
import sentry_sdk

from payplan.requests import nomba_request

def transfer(amount, account_number, account_name, bank_code, merchant_tx_ref, sender_name, narration):
    payload = {
        "amount": float(amount),
        "accountNumber": account_number,
        "accountName": account_name,
        "bankCode": bank_code,
        "merchantTxRef": merchant_tx_ref,
        "senderName": sender_name,
        "narration": narration
    }
    
    try:
        response = nomba_request("POST", "transfers", payload=payload)
        data = response.json()
        
        if response.ok and data.get("code") == "00":
            return data.get("data")
        
        sentry_sdk.logger.error("Nomba transfer failed", extra={"response": data, "payload": payload})
        raise Exception(f"Nomba transfer failed: {data.get('message', 'Unknown error')}")
    
    except Exception as e:
        sentry_sdk.logger.error("Unable to reach Nomba transfer service", extra={"error": str(e)})
        raise Exception("Unable to reach Nomba transfer service") from e
