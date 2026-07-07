import requests
import sentry_sdk

from payplan.requests import nomba_request
from transactions.exceptions import NombaConnectionError

from .exceptions import NombaBankLookupError


def lookup_bank_account(account_number, bank_code):
    """
    Resolve the account name for a (account_number, bank_code) pair via Nomba.

    Calls `POST /v1/transfers/bank/lookup` and returns the resolved account name.
    Raises NombaBankLookupError on a definitive rejection from Nomba.
    Connection-level errors propagate as NombaConnectionError so callers can
    distinguish "Nomba said no" from "we couldn't reach Nomba at all".
    """
    payload = {
        "accountNumber": account_number,
        "bankCode": bank_code,
    }

    try:
        response = nomba_request("POST", "transfers/bank/lookup", payload=payload, version="v1")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        sentry_sdk.logger.error(
            "Nomba bank lookup connection failed",
            attributes={"error": str(e)},
        )
        raise NombaConnectionError(f"Unable to reach Nomba: {e}") from e

    try:
        data = response.json()
    except (ValueError, TypeError) as e:
        sentry_sdk.logger.error(
            "Nomba bank lookup returned non-JSON response",
            attributes={"status_code": response.status_code},
        )
        raise NombaBankLookupError("Nomba bank lookup returned malformed response") from e

    if not response.ok or data.get("code") != "00":
        sentry_sdk.logger.error(
            "Nomba bank lookup rejected",
            attributes={"response": data, "account_number": account_number, "bank_code": bank_code},
        )
        message = data.get("message") or data.get("description") or "Unknown error"
        raise NombaBankLookupError(message)

    inner = data.get("data") or {}
    account_name = inner.get("accountName")
    if not account_name:
        sentry_sdk.logger.error(
            "Nomba bank lookup response missing accountName",
            attributes={"response": data},
        )
        raise NombaBankLookupError("Nomba bank lookup response missing accountName")

    return account_name
