from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import requests as real_requests
from django.test import TestCase, override_settings

from payplan.nomba_auth import (
    NombaAuthenticationError,
    _active_env,
    _active_credentials,
    get_access_token,
    force_refresh,
)
from payplan.tests.fake_redis import FakeRedis


SAMPLE_AUTH_RESPONSE = {
    "code": "00",
    "description": "Successful",
    "status": False,
    "data": {
        "access_token": "sample_token_abc",
        "businessId": "acct-1",
        "refresh_token": "rt-1",
        "expiresAt": "2099-12-31T23:59:59.000Z",
    },
}


def _mock_response(json_body=None, status_code=200, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_body
    return response


class TestActiveEnv(TestCase):
    @override_settings(ENVIRONMENT='PRODUCTION')
    def test_returns_live_in_production(self):
        self.assertEqual(_active_env(), 'live')

    @override_settings(ENVIRONMENT='DEVELOPMENT')
    def test_returns_test_by_default(self):
        self.assertEqual(_active_env(), 'test')

    @override_settings(ENVIRONMENT='production')
    def test_live_check_is_case_insensitive(self):
        self.assertEqual(_active_env(), 'live')

    @override_settings(ENVIRONMENT=None)
    def test_returns_test_when_env_unset(self):
        self.assertEqual(_active_env(), 'test')


class TestActiveCredentials(TestCase):
    @override_settings(
        ENVIRONMENT='PRODUCTION',
        NOMBA_LIVE_CLIENT_ID='live_id',
        NOMBA_LIVE_PRIVATE_KEY='live_secret',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_LIVE_BASE_URL='https://api.nomba.com',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    def test_returns_live_credentials_in_production(self):
        creds = _active_credentials()
        self.assertEqual(creds['client_id'], 'live_id')
        self.assertEqual(creds['client_secret'], 'live_secret')
        self.assertEqual(creds['base_url'], 'https://api.nomba.com')
        self.assertEqual(creds['account_id'], 'acct_123')

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_LIVE_CLIENT_ID='live_id',
        NOMBA_LIVE_PRIVATE_KEY='live_secret',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_LIVE_BASE_URL='https://api.nomba.com',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    def test_returns_test_credentials_in_development(self):
        creds = _active_credentials()
        self.assertEqual(creds['client_id'], 'test_id')
        self.assertEqual(creds['client_secret'], 'test_secret')
        self.assertEqual(creds['base_url'], 'https://sandbox.nomba.com')
        self.assertEqual(creds['account_id'], 'acct_123')


class TestGetAccessToken(TestCase):
    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_returns_token_on_successful_auth(self, mock_post, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_post.return_value = _mock_response(SAMPLE_AUTH_RESPONSE)

        token = get_access_token()

        self.assertEqual(token, 'sample_token_abc')
        mock_post.assert_called_once()
        called_kwargs = mock_post.call_args.kwargs
        self.assertEqual(called_kwargs['json']['grant_type'], 'client_credentials')
        self.assertEqual(called_kwargs['json']['client_id'], 'test_id')
        self.assertEqual(called_kwargs['json']['client_secret'], 'test_secret')

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_caches_token_with_refresh_margin_ttl(self, mock_post, mock_redis_client):
        fake = FakeRedis()
        mock_redis_client.return_value = fake
        one_hour_from_now = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        body = {
            "code": "00", "status": False,
            "data": {**SAMPLE_AUTH_RESPONSE['data'], "expiresAt": one_hour_from_now}
        }
        mock_post.return_value = _mock_response(body)

        get_access_token()

        # Cache TTL should be ~3300s (3600 - 300 margin), verify via fake.ttl
        self.assertAlmostEqual(fake.ttl('nomba:access_token:test'), 3300, delta=2)

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_uses_cached_token_when_still_valid(self, mock_post, mock_redis_client):
        fake = FakeRedis()
        future = (datetime.now(tz=timezone.utc) + timedelta(minutes=10)).isoformat()
        fake.set('nomba:access_token:test', f'{{"token": "cached_tok", "expires_at": "{future}"}}', ex=600)
        mock_redis_client.return_value = fake

        token = get_access_token()

        self.assertEqual(token, 'cached_tok')
        mock_post.assert_not_called()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_refreshes_token_when_within_margin(self, mock_post, mock_redis_client):
        fake = FakeRedis()
        near_future = (datetime.now(tz=timezone.utc) + timedelta(seconds=60)).isoformat()
        fake.set('nomba:access_token:test', f'{{"token": "stale_tok", "expires_at": "{near_future}"}}', ex=60)
        mock_redis_client.return_value = fake
        mock_post.return_value = _mock_response(SAMPLE_AUTH_RESPONSE)

        token = get_access_token()

        self.assertEqual(token, 'sample_token_abc')
        mock_post.assert_called_once()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_raises_NombaAuthenticationError_on_403(self, mock_post, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_post.return_value = _mock_response(status_code=403, text='forbidden body')

        with self.assertRaises(NombaAuthenticationError):
            get_access_token()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_raises_NombaAuthenticationError_on_malformed_response(self, mock_post, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_post.return_value = _mock_response({"code": "00", "data": {"access_token": "x"}})

        with self.assertRaises(NombaAuthenticationError):
            get_access_token()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_raises_NombaAuthenticationError_on_network_error(self, mock_post, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_post.side_effect = real_requests.exceptions.ConnectionError("nope")

        with self.assertRaises(NombaAuthenticationError):
            get_access_token()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_single_flight_loser_waits_for_winner(self, mock_post, mock_redis_client):
        fake = FakeRedis()
        # Pre-acquire the lock so the contender loses
        fake.set('nomba:token_lock:test', b'1', nx=True, ex=10)
        # Pre-populate cache with a valid token (the winner has done their job)
        future = (datetime.now(tz=timezone.utc) + timedelta(minutes=10)).isoformat()
        fake.set('nomba:access_token:test', f'{{"token": "winner_tok", "expires_at": "{future}"}}', ex=600)
        mock_redis_client.return_value = fake
        mock_post.return_value = _mock_response(SAMPLE_AUTH_RESPONSE)

        token = get_access_token()

        # Contender waited for the winner, did NOT make its own auth call
        self.assertEqual(token, 'winner_tok')
        mock_post.assert_not_called()

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_single_flight_only_one_auth_call_under_contention(self, mock_post, mock_redis_client):
        # Simulate two concurrent requests: both call get_access_token()
        # The first acquires the lock and populates the cache; the second
        # loses the lock and should find the populated cache.
        fake = FakeRedis()
        mock_redis_client.return_value = fake

        call_count = {'n': 0}
        original_set = fake.set

        def counted_set(key, value, ex=None, nx=False):
            # Only the first call to /v1/auth/token/issue should succeed
            if key == 'nomba:token_lock:test' and nx:
                if call_count['n'] > 0:
                    return False
                call_count['n'] += 1
            return original_set(key, value, ex=ex, nx=nx)

        fake.set = counted_set

        def auth_then_populate(*args, **kwargs):
            # Simulate the winner populating the cache after their auth call
            response = _mock_response(SAMPLE_AUTH_RESPONSE)
            future = (datetime.now(tz=timezone.utc) + timedelta(minutes=10)).isoformat()
            fake.set('nomba:access_token:test',
                     f'{{"token": "sample_token_abc", "expires_at": "{future}"}}',
                     ex=600)
            return response
        mock_post.side_effect = auth_then_populate

        # Two near-simultaneous callers
        token1 = get_access_token()
        token2 = get_access_token()

        self.assertEqual(token1, 'sample_token_abc')
        self.assertEqual(token2, 'sample_token_abc')
        # Only one real auth call happened
        self.assertEqual(mock_post.call_count, 1)


class TestForceRefresh(TestCase):
    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_clears_cache_and_refetches(self, mock_post, mock_redis_client):
        fake = FakeRedis()
        # Pre-populate with a still-valid token
        future = (datetime.now(tz=timezone.utc) + timedelta(minutes=30)).isoformat()
        fake.set('nomba:access_token:test', f'{{"token": "old", "expires_at": "{future}"}}', ex=1800)
        fake.set('nomba:token_lock:test', b'1', ex=10)
        mock_redis_client.return_value = fake
        mock_post.return_value = _mock_response(SAMPLE_AUTH_RESPONSE)

        token = force_refresh()

        self.assertEqual(token, 'sample_token_abc')
        # Cache and lock keys were deleted before refetch, then re-populated with the new token
        cached = fake.get('nomba:access_token:test')
        self.assertIsNotNone(cached)
        self.assertIn('sample_token_abc', cached)
        self.assertIsNone(fake.get('nomba:token_lock:test'))
        mock_post.assert_called_once()


class TestNoSecretLogging(TestCase):
    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='SENSITIVE_SECRET_VALUE',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth.sentry_sdk')
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.nomba_auth.requests.post')
    def test_no_secret_in_sentry_log_on_auth_failure(self, mock_post, mock_redis_client, mock_sentry):
        mock_redis_client.return_value = FakeRedis()
        mock_post.return_value = _mock_response(status_code=403, text='forbidden body')

        with self.assertRaises(NombaAuthenticationError):
            get_access_token()

        sensitive = 'SENSITIVE_SECRET_VALUE'
        all_calls = []
        for method in ('logger.error', 'logger.warning', 'logger.info', 'capture_message', 'capture_exception'):
            mock_method = getattr(mock_sentry, method, None)
            if mock_method and mock_method.called:
                all_calls.extend(mock_method.call_args_list)
        for call in all_calls:
            rendered = str(call)
            self.assertNotIn(sensitive, rendered, f"Secret leaked into Sentry log: {rendered}")
