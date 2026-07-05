from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from payplan.nomba_auth import NombaAuthenticationError
from payplan.requests import nomba_request
from payplan.tests.fake_redis import FakeRedis


SAMPLE_AUTH_RESPONSE = {
    "code": "00",
    "description": "Successful",
    "status": False,
    "data": {
        "access_token": "tok_123",
        "businessId": "acct-1",
        "refresh_token": "rt-1",
        "expiresAt": "2099-12-31T23:59:59.000Z",
    },
}


def _mock_response(status_code=200, json_body=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_body or {}
    return r


class TestNombaRequest(TestCase):
    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_uses_test_base_url_in_development(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, {"data": "ok"})

        nomba_request("GET", "transfers")

        called_url = mock_request.call_args.args[1] if len(mock_request.call_args.args) > 1 else mock_request.call_args.kwargs.get('url')
        self.assertIsNotNone(called_url)
        self.assertTrue(called_url.startswith('https://sandbox.nomba.com/v2/transfers'))

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
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_uses_live_base_url_in_production(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, {"data": "ok"})

        nomba_request("GET", "transfers")

        called_url = mock_request.call_args.args[1] if len(mock_request.call_args.args) > 1 else mock_request.call_args.kwargs.get('url')
        self.assertIsNotNone(called_url)
        self.assertTrue(called_url.startswith('https://api.nomba.com/v2/transfers'))

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.requests.requests.request')
    @patch('payplan.requests.get_access_token')
    def test_includes_bearer_token_in_authorization_header(self, mock_get_token, mock_request, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_get_token.return_value = 'my_bearer_token'
        mock_request.return_value = _mock_response(200, {"data": "ok"})

        nomba_request("GET", "transfers")

        sent_headers = mock_request.call_args.kwargs['headers']
        self.assertEqual(sent_headers['Authorization'], 'Bearer my_bearer_token')
        self.assertEqual(sent_headers['accountId'], 'acct_123')
        self.assertEqual(sent_headers['Content-Type'], 'application/json')

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.requests.requests.request')
    @patch('payplan.requests.force_refresh')
    @patch('payplan.requests.get_access_token')
    def test_retries_once_on_401_then_succeeds(self, mock_get_token, mock_force_refresh, mock_request, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        # First token use -> 401, then force_refresh -> second token -> 200
        mock_get_token.side_effect = ['old_token', 'new_token']
        mock_force_refresh.return_value = 'new_token'
        mock_request.side_effect = [
            _mock_response(401, text='token expired'),
            _mock_response(200, {"data": "ok"}),
        ]

        response = nomba_request("GET", "transfers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_count, 2)
        # Second call should use the new token
        second_call_headers = mock_request.call_args_list[1].kwargs['headers']
        self.assertEqual(second_call_headers['Authorization'], 'Bearer new_token')

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.requests.requests.request')
    @patch('payplan.requests.force_refresh')
    @patch('payplan.requests.get_access_token')
    def test_raises_NombaAuthenticationError_after_retry_also_401(self, mock_get_token, mock_force_refresh, mock_request, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_get_token.side_effect = ['old_token', 'new_token']
        mock_force_refresh.return_value = 'new_token'
        mock_request.side_effect = [
            _mock_response(401, text='token expired'),
            _mock_response(401, text='still bad'),
        ]

        with self.assertRaises(NombaAuthenticationError):
            nomba_request("GET", "transfers")

        # Only one retry, not a loop
        self.assertEqual(mock_request.call_count, 2)

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.requests.requests.request')
    @patch('payplan.requests.force_refresh')
    @patch('payplan.requests.get_access_token')
    def test_force_refresh_failure_raises_auth_error(self, mock_get_token, mock_force_refresh, mock_request, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_get_token.return_value = 'old_token'
        mock_force_refresh.side_effect = NombaAuthenticationError("cred wrong")
        mock_request.return_value = _mock_response(401, text='token expired')

        with self.assertRaises(NombaAuthenticationError):
            nomba_request("GET", "transfers")

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.nomba_auth._redis_client')
    @patch('payplan.requests.requests.request')
    @patch('payplan.requests.sentry_sdk')
    @patch('payplan.requests.get_access_token')
    def test_no_secret_logged_on_401_retry(self, mock_get_token, mock_sentry, mock_request, mock_redis_client):
        mock_redis_client.return_value = FakeRedis()
        mock_get_token.side_effect = ['old_token']
        mock_force_refresh = MagicMock(side_effect=NombaAuthenticationError("boom"))
        with patch('payplan.requests.force_refresh', mock_force_refresh):
            mock_request.return_value = _mock_response(401, text='token expired marker')
            with self.assertRaises(NombaAuthenticationError):
                nomba_request("GET", "transfers")

        sensitive_markers = ['SENSITIVE_TOKEN', 'SENSITIVE_SECRET']
        all_calls = []
        for method in ('logger.error', 'logger.warning', 'logger.info', 'capture_message', 'capture_exception'):
            mock_method = getattr(mock_sentry, method, None)
            if mock_method and mock_method.called:
                all_calls.extend(mock_method.call_args_list)
        for call in all_calls:
            rendered = str(call)
            for marker in sensitive_markers:
                self.assertNotIn(marker, rendered, f"Sensitive marker {marker} leaked into Sentry log: {rendered}")
