from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from plans.factories import PayPlanFactory, UserFactory
from plans.models import PayPlan
from transactions.models import Transaction, TransactionEvent, DunningAttempt
from transactions.services import (
    set_transaction_succeeded,
    record_transaction,
    initiate_payout,
    handle_payout_failure,
    schedule_next_payout_attempt,
)
from transactions.exceptions import NombaTransferRejected, NombaConnectionError


def _make_txn_and_attempt(plan, cycle=1):
    txn = record_transaction(
        plan=plan,
        charge_reference=f"engine_ref_{cycle}",
        amount=plan.amount,
        cycle_number=cycle,
        status=Transaction.Status.CHARGE_SUCCESS,
        event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
    )
    attempt = DunningAttempt.objects.create(
        transaction=txn,
        attempt_number=0,
        scheduled_at=txn.created_at,
        status=DunningAttempt.Status.AWAITING_CONFIRMATION,
    )
    return txn, attempt


class TestHandlePayoutFailure(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user, status=PayPlan.Status.ACTIVE)
        self.txn, self.attempt = _make_txn_and_attempt(self.plan)

    @patch('transactions.services.send_payout_failure_email')
    def test_marks_attempt_failed_with_reason(self, mock_email):
        handle_payout_failure(self.attempt, "Bank rejected transfer")
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, DunningAttempt.Status.FAILED)
        self.assertEqual(self.attempt.failure_reason, "Bank rejected transfer")

    @patch('transactions.services.send_payout_failure_email')
    def test_marks_transaction_payout_failed(self, mock_email):
        handle_payout_failure(self.attempt, "Bank rejected transfer")
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, Transaction.Status.PAYOUT_FAILED)

    @patch('transactions.services.send_payout_failure_email')
    @patch('transactions.services.schedule_next_payout_attempt')
    def test_within_retries_schedules_next_attempt(self, mock_schedule, mock_email):
        handle_payout_failure(self.attempt, "Bank rejected transfer")
        mock_schedule.assert_called_once_with(self.attempt)
        mock_email.assert_not_called()

    @patch('transactions.services.send_payout_failure_email')
    @patch('transactions.services.schedule_next_payout_attempt')
    def test_at_retry_boundary_pauses_plan_and_emails(self, mock_schedule, mock_email):
        self.attempt.attempt_number = len([1, 4, 12])
        self.attempt.save(update_fields=['attempt_number'])

        handle_payout_failure(self.attempt, "Bank rejected transfer")

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, PayPlan.Status.PAUSED)
        mock_schedule.assert_not_called()
        mock_email.assert_called_once()
        kwargs = mock_email.call_args.kwargs
        self.assertEqual(kwargs['plan'], self.plan)
        self.assertEqual(kwargs['transaction'], self.txn)
        self.assertEqual(kwargs['attempt'], self.attempt)
        self.assertEqual(kwargs['reason'], "Bank rejected transfer")


class TestInitiatePayout(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user, status=PayPlan.Status.ACTIVE)
        self.txn, self.attempt = _make_txn_and_attempt(self.plan)

    @patch('transactions.requests.nomba_request')
    def test_happy_path_stores_payout_reference(self, mock_nomba):
        mock_nomba.return_value.json.return_value = {
            "code": "00",
            "data": {"id": "PAYOUT_XYZ_123"},
        }
        mock_nomba.return_value.ok = True

        initiate_payout(self.attempt)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.payout_reference, "PAYOUT_XYZ_123")
        self.assertEqual(self.attempt.status, DunningAttempt.Status.AWAITING_CONFIRMATION)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, Transaction.Status.PAYOUT_PENDING)

    @patch('transactions.requests.nomba_request')
    def test_nomba_rejection_triggers_failure(self, mock_nomba):
        from transactions.requests import transfer as transfer_fn
        mock_nomba.return_value.json.return_value = {
            "code": "99",
            "message": "Insufficient funds",
        }
        mock_nomba.return_value.ok = True

        with self.assertRaises(NombaTransferRejected):
            transfer_fn(
                amount=100, account_number="x", account_name="y",
                bank_code="z", merchant_tx_ref="m", sender_name="s", narration="n",
            )
