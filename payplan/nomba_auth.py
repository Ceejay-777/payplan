import json
import logging
import time
from datetime import datetime, timezone as dt_timezone, timedelta

import redis
import requests
from requests.exceptions import RequestException
import sentry_sdk
from django.conf import settings

logger = logging.getLogger(__name__)

NOMBA_AUTH_URL = "https://api.nomba.com/v1/auth/token/issue"
REFRESH_MARGIN_SECONDS = 300
SINGLE_FLIGHT_TIMEOUT_SECONDS = 5
SINGLE_FLIGHT_POLL_INTERVAL = 0.05
SINGLE_FLIGHT_LOCK_TTL_SECONDS = 10
AUTH_REQUEST_TIMEOUT_SECONDS = 10


class NombaAuthenticationError(Exception):
    """Raised when Nomba authentication fails (token endpoint or credential issue).

    Distinct from business-call failures like NombaConnectionError/NombaTransferRejected.
    A failed token fetch is an infrastructure failure, not a business outcome.
    """


def _redis_client():
    return redis.Redis.from_url(settings.REDIS_URL)


def _active_env():
    return 'live' if (settings.ENVIRONMENT or '').upper() == 'PRODUCTION' else 'test'


def _active_credentials():
    env = _active_env()
    if env == 'live':
        return {
            'client_id': settings.NOMBA_LIVE_CLIENT_ID,
            'client_secret': settings.NOMBA_LIVE_PRIVATE_KEY,
            'account_id': settings.NOMBA_ACCOUNT_ID,
            'base_url': settings.NOMBA_LIVE_BASE_URL,
        }
    return {
        'client_id': settings.NOMBA_TEST_CLIENT_ID,
        'client_secret': settings.NOMBA_TEST_PRIVATE_KEY,
        'account_id': settings.NOMBA_ACCOUNT_ID,
        'base_url': settings.NOMBA_TEST_BASE_URL,
    }


def _cache_key():
    return f"nomba:access_token:{_active_env()}"


def _lock_key():
    return f"nomba:token_lock:{_active_env()}"


def _parse_expires_at(expires_at_str):
    parsed = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _fetch_token_from_nomba():
    creds = _active_credentials()
    payload = {
        'grant_type': 'client_credentials',
        'client_id': creds['client_id'],
        'client_secret': creds['client_secret'],
    }
    headers = {
        'Content-Type': 'application/json',
        'accountId': creds['account_id'],
    }
    try:
        response = requests.post(
            NOMBA_AUTH_URL,
            json=payload,
            headers=headers,
            timeout=AUTH_REQUEST_TIMEOUT_SECONDS,
        )
    except RequestException as e:
        sentry_sdk.logger.error(
            "Nomba auth request failed",
            attributes={"error_type": type(e).__name__},
        )
        raise NombaAuthenticationError("Unable to reach Nomba auth endpoint") from e

    if response.status_code != 200:
        sentry_sdk.logger.error(
            "Nomba auth returned non-200",
            attributes={"status_code": response.status_code},
        )
        raise NombaAuthenticationError(
            f"Nomba auth failed with HTTP {response.status_code}"
        )

    try:
        body = response.json()
        token_data = body.get('data') or {}
        access_token = token_data['access_token']
        expires_at_str = token_data['expiresAt']
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        sentry_sdk.logger.error(
            "Nomba auth response missing required fields",
            attributes={"error_type": type(e).__name__},
        )
        raise NombaAuthenticationError("Nomba auth response malformed") from e

    if not access_token or not expires_at_str:
        raise NombaAuthenticationError("Nomba auth response missing token/expiresAt")

    return {
        'token': access_token,
        'expires_at': _parse_expires_at(expires_at_str),
    }


def _store_token(entry):
    now = datetime.now(tz=dt_timezone.utc)
    refresh_at = entry['expires_at'] - timedelta(seconds=REFRESH_MARGIN_SECONDS)
    cache_ttl = max(int((refresh_at - now).total_seconds()), 1)
    payload = json.dumps({
        'token': entry['token'],
        'expires_at': entry['expires_at'].isoformat(),
    })
    _redis_client().set(_cache_key(), payload, ex=cache_ttl)


def _read_cached_token():
    raw = _redis_client().get(_cache_key())
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return {
            'token': data['token'],
            'expires_at': datetime.fromisoformat(data['expires_at']),
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _is_still_valid(entry):
    if not entry:
        return False
    now = datetime.now(tz=dt_timezone.utc)
    return entry['expires_at'] > now + timedelta(seconds=REFRESH_MARGIN_SECONDS)


def get_access_token():
    cached = _read_cached_token()
    if _is_still_valid(cached):
        return cached['token']

    r = _redis_client()
    got_lock = r.set(_lock_key(), b'1', nx=True, ex=SINGLE_FLIGHT_LOCK_TTL_SECONDS)
    if got_lock:
        try:
            entry = _fetch_token_from_nomba()
            _store_token(entry)
            return entry['token']
        finally:
            r.delete(_lock_key())
    else:
        deadline = time.time() + SINGLE_FLIGHT_TIMEOUT_SECONDS
        while time.time() < deadline:
            time.sleep(SINGLE_FLIGHT_POLL_INTERVAL)
            cached = _read_cached_token()
            if _is_still_valid(cached):
                return cached['token']
        entry = _fetch_token_from_nomba()
        _store_token(entry)
        return entry['token']


def force_refresh():
    r = _redis_client()
    r.delete(_cache_key())
    r.delete(_lock_key())
    return get_access_token()
