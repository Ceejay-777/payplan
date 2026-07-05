import logging

import requests
import sentry_sdk
from django.conf import settings

from payplan.nomba_auth import (
    NombaAuthenticationError,
    _active_credentials,
    force_refresh,
    get_access_token,
)

logger = logging.getLogger(__name__)


def nomba_request(method, endpoint, payload=None, timeout=10, version="v2"):
    """
    Make a request to the Nomba API using a token from the auth service.
    Retries once on 401 by forcing a token refresh.

    The base URL is selected from NOMBA_TEST_BASE_URL (sandbox) or
    NOMBA_LIVE_BASE_URL (production) based on settings.ENVIRONMENT.
    The API version defaults to "v2" to match the documented base;
    pass version="v1" for endpoints exposed only on the legacy v1 surface.
    """
    creds = _active_credentials()
    url = f"{creds['base_url']}/{version}/{endpoint}/"

    def _do_call(token):
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'accountId': creds['account_id'],
        }
        return requests.request(method, url, headers=headers, json=payload, timeout=timeout)

    try:
        token = get_access_token()
        response = _do_call(token)
    except requests.exceptions.RequestException as e:
        sentry_sdk.logger.error(
            "Nomba request failed",
            attributes={"error_type": type(e).__name__, "endpoint": endpoint},
        )
        raise

    if response.status_code == 401:
        try:
            new_token = force_refresh()
        except NombaAuthenticationError:
            sentry_sdk.logger.error(
                "Nomba 401 retry: token refresh failed",
                attributes={"endpoint": endpoint},
            )
            raise
        response = _do_call(new_token)
        if response.status_code == 401:
            sentry_sdk.logger.error(
                "Nomba 401 retry: still unauthorized after refresh",
                attributes={"endpoint": endpoint},
            )
            raise NombaAuthenticationError(
                f"Nomba rejected token after refresh on {endpoint}"
            )

    return response


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
