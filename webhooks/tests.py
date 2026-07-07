import hashlib
import hmac
import json
import base64
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from plans.factories import PayPlanFactory, UserFactory
from transactions.models import Transaction, TransactionEvent, DunningAttempt
from transactions.services import record_transaction
from webhooks.payout_handlers import handle_payout_success, handle_payout_refund
from webhooks.webhooks import NombaWebhookView


def _make_attempt_with_payout_ref(plan, payout_reference, attempt_number=0, status=None):
    txn = record_transaction(
        plan=plan,
        charge_reference="engine_ref_1",
        amount=plan.amount,
        cycle_number=1,
        status=Transaction.Status.CHARGE_SUCCESS,
        event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
    )
    attempt = DunningAttempt.objects.create(
        transaction=txn,
        attempt_number=attempt_number,
        scheduled_at=txn.created_at,
        status=status or DunningAttempt.Status.AWAITING_CONFIRMATION,
        payout_reference=payout_reference,
    )
    return txn, attempt


class TestHandlePayoutSuccess(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user)
        self.txn, self.attempt = _make_attempt_with_payout_ref(self.plan, "PAYOUT_ABC")

    def test_marks_attempt_and_transaction_succeeded(self):
        handle_payout_success({"id": "PAYOUT_ABC"})

        self.attempt.refresh_from_db()
        self.txn.refresh_from_db()
        self.assertEqual(self.attempt.status, DunningAttempt.Status.SUCCESS)
        self.assertEqual(self.txn.status, Transaction.Status.PAYOUT_SUCCESS)

    def test_idempotent_when_attempt_already_success(self):
        self.attempt.status = DunningAttempt.Status.SUCCESS
        self.attempt.save(update_fields=['status'])

        with patch('webhooks.payout_handlers.set_transaction_succeeded') as mock_set:
            handle_payout_success({"id": "PAYOUT_ABC"})
            mock_set.assert_not_called()

    def test_raises_on_unknown_reference(self):
        with self.assertRaises(DunningAttempt.DoesNotExist):
            handle_payout_success({"id": "DOES_NOT_EXIST"})


class TestHandlePayoutRefund(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user)
        self.txn, self.attempt = _make_attempt_with_payout_ref(self.plan, "PAYOUT_XYZ")

    @patch('webhooks.payout_handlers.handle_payout_failure')
    def test_delegates_to_failure_handler_with_reason(self, mock_failure):
        handle_payout_refund({"id": "PAYOUT_XYZ", "reason": "Insufficient funds"})
        mock_failure.assert_called_once()
        args, kwargs = mock_failure.call_args
        self.assertEqual(args[0], self.attempt)
        self.assertEqual(kwargs.get('reason') or args[1], "Insufficient funds")

    def test_skips_when_attempt_already_terminal(self):
        self.attempt.status = DunningAttempt.Status.SUCCESS
        self.attempt.save(update_fields=['status'])

        with patch('webhooks.payout_handlers.handle_payout_failure') as mock_failure:
            handle_payout_refund({"id": "PAYOUT_XYZ", "reason": "x"})
            mock_failure.assert_not_called()

    def test_raises_on_unknown_reference(self):
        with self.assertRaises(DunningAttempt.DoesNotExist):
            handle_payout_refund({"id": "DOES_NOT_EXIST", "reason": "x"})


def _sign_nomba_payload(payload_dict, secret, timestamp="1700000000"):
    """Recreate Nomba's webhook signature scheme from webhooks.py."""
    event_type = payload_dict.get('event_type', '')
    request_id = payload_dict.get('requestId', '')
    data = payload_dict.get('data', {})
    merchant = data.get('merchant', {})
    transaction = data.get('transaction', {})

    response_code = transaction.get('responseCode', '')
    if response_code == "null":
        response_code = ""

    hashing_payload = ":".join([
        event_type,
        request_id,
        merchant.get('userId', ''),
        merchant.get('walletId', ''),
        transaction.get('transactionId', ''),
        transaction.get('type', ''),
        transaction.get('time', ''),
        response_code,
        timestamp,
    ])

    expected = hmac.new(
        secret.encode(),
        hashing_payload.encode(),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(expected).decode()


@override_settings(NOMBA_WEBHOOK_SECRET="test_secret")
class TestNombaWebhookSignature(TestCase):
    def setUp(self):
        # webhooks.py reads NOMBA_WEBHOOK_SECRET at import time, so override_settings
        # alone doesn't change the module-level constant it actually uses.
        self._secret_patcher = patch("webhooks.webhooks.nomba_webhook_secret", "test_secret")
        self._secret_patcher.start()
        self.factory = APIRequestFactory()
        self.view = NombaWebhookView.as_view()
        self.payload = {
            "event_type": "payout_success",
            "requestId": "req_1",
            "data": {
                "id": "PAYOUT_REF_1",
                "merchant": {"userId": "u1", "walletId": "w1"},
                "transaction": {
                    "transactionId": "t1",
                    "type": "transfer",
                    "time": "2026-07-05T00:00:00Z",
                    "responseCode": "00",
                },
            },
        }

    def tearDown(self):
        self._secret_patcher.stop()

    def test_valid_signature_passes(self):
        user = UserFactory()
        plan = PayPlanFactory(creator=user)
        _make_attempt_with_payout_ref(plan, "PAYOUT_REF_1")

        timestamp = "1700000000"
        sig = _sign_nomba_payload(self.payload, "test_secret", timestamp)
        body = json.dumps(self.payload).encode()
        request = self.factory.post(
            "/webhooks/nomba",
            data=body,
            content_type="application/json",
            HTTP_NOMBA_SIGNATURE=sig,
            HTTP_NOMBA_TIMESTAMP=timestamp,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200, response.data)

    def test_missing_signature_rejected(self):
        body = json.dumps(self.payload).encode()
        request = self.factory.post(
            "/webhooks/nomba",
            data=body,
            content_type="application/json",
            HTTP_NOMBA_TIMESTAMP="1700000000",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

    def test_tampered_signature_rejected(self):
        body = json.dumps(self.payload).encode()
        request = self.factory.post(
            "/webhooks/nomba",
            data=body,
            content_type="application/json",
            HTTP_NOMBA_SIGNATURE="not-a-real-signature",
            HTTP_NOMBA_TIMESTAMP="1700000000",
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

    def test_unknown_event_type_returns_200_without_handler(self):
        timestamp = "1700000000"
        self.payload["event_type"] = "something_else"
        sig = _sign_nomba_payload(self.payload, "test_secret", timestamp)
        body = json.dumps(self.payload).encode()
        request = self.factory.post(
            "/webhooks/nomba",
            data=body,
            content_type="application/json",
            HTTP_NOMBA_SIGNATURE=sig,
            HTTP_NOMBA_TIMESTAMP=timestamp,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
