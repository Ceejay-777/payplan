import requests
from django.conf import settings
import sentry_sdk

from payplan.requests import nomba_request
from transactions.exceptions import NombaConnectionError, NombaTransferRejected

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
        
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        sentry_sdk.logger.error(
            "Nomba transfer connection failed, outcome unknown",
            attributes={"merchant_tx_ref": merchant_tx_ref, "error": str(e)},
        )
        raise NombaConnectionError(f"Unable to reach Nomba: {e}") from e
    
    data = response.json()
        
    if response.ok and data.get("code") == "00":
        return data.get("data")
    
    sentry_sdk.logger.error(
        "Nomba transfer rejected",
        attributes={"response": data, "merchant_tx_ref": merchant_tx_ref},
    )
    raise NombaTransferRejected(data.get("message", "Unknown error"))
    
