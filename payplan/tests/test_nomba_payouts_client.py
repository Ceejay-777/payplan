from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from payplan.nomba_payouts.client import lookup_bank_account
from payplan.nomba_payouts.exceptions import NombaBankLookupError
from payplan.tests.fake_redis import FakeRedis
from transactions.exceptions import NombaConnectionError


def _mock_response(status_code=200, json_body=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_body or {}
    r.ok = 200 <= status_code < 300
    return r


SAMPLE_LOOKUP_RESPONSE = {
    "code": "00",
    "description": "Success",
    "data": {
        "accountNumber": "0554772814",
        "accountName": "M.A Animashaun",
    },
}


class TestLookupBankAccount(TestCase):
    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_returns_account_name_on_success(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, SAMPLE_LOOKUP_RESPONSE)

        result = lookup_bank_account("0554772814", "053")

        self.assertEqual(result, "M.A Animashaun")

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_uses_v1_endpoint(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, SAMPLE_LOOKUP_RESPONSE)

        lookup_bank_account("0554772814", "053")

        called_url = mock_request.call_args.kwargs.get('url') or mock_request.call_args.args[1]
        self.assertIsNotNone(called_url)
        self.assertTrue(
            called_url.startswith('https://sandbox.nomba.com/v1/transfers/bank/lookup'),
            f"Expected v1 endpoint, got: {called_url}",
        )

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_sends_correct_payload(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, SAMPLE_LOOKUP_RESPONSE)

        lookup_bank_account("0554772814", "053")

        sent_payload = mock_request.call_args.kwargs.get('json')
        self.assertEqual(sent_payload, {"accountNumber": "0554772814", "bankCode": "053"})

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_raises_lookup_error_on_non_00_code(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(200, {
            "code": "99",
            "description": "Account not found",
            "message": "Account not found",
        })

        with self.assertRaises(NombaBankLookupError):
            lookup_bank_account("0554772814", "053")

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_raises_lookup_error_on_http_error(self, mock_request, mock_get_token):
        mock_get_token.return_value = 't'
        mock_request.return_value = _mock_response(500, {"message": "Server error"})

        with self.assertRaises(NombaBankLookupError):
            lookup_bank_account("0554772814", "053")

    @override_settings(
        ENVIRONMENT='DEVELOPMENT',
        NOMBA_TEST_CLIENT_ID='test_id',
        NOMBA_TEST_PRIVATE_KEY='test_secret',
        NOMBA_ACCOUNT_ID='acct_123',
        NOMBA_TEST_BASE_URL='https://sandbox.nomba.com',
    )
    @patch('payplan.requests.get_access_token')
    @patch('payplan.requests.requests.request')
    def test_propagates_connection_error(self, mock_request, mock_get_token):
        import requests as real_requests
        mock_get_token.return_value = 't'
        mock_request.side_effect = real_requests.exceptions.ConnectionError("boom")

        with self.assertRaises(NombaConnectionError):
            lookup_bank_account("0554772814", "053")
