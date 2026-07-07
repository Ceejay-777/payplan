from unittest.mock import patch

from django.test import TestCase, override_settings
from django.template.loader import render_to_string

from payplan.nomba_payouts.emails import send_payout_success_email, send_payout_failure_email
from plans.factories import PayPlanFactory, UserFactory
from transactions.models import Transaction, DunningAttempt, TransactionEvent
from transactions.services import record_transaction, create_and_run_first_payout_attempt


class TestPayoutEmails(TestCase):
    def setUp(self):
        self.user = UserFactory(email="creator@example.com")
        self.plan = PayPlanFactory(creator=self.user, title="Lagos Apartment", amount=50000.00)

    def _make_transaction_and_attempt(self):
        txn = record_transaction(
            plan=self.plan,
            charge_reference="engine_ref_1",
            amount=self.plan.amount,
            cycle_number=1,
            status=Transaction.Status.CHARGE_SUCCESS,
            event_type=TransactionEvent.EventTypes.CHARGE_SUCCEEDED,
        )
        attempt = DunningAttempt.objects.create(
            transaction=txn,
            attempt_number=0,
            scheduled_at=txn.created_at,
            status=DunningAttempt.Status.SUCCESS,
            payout_reference="PAYOUT_ABC",
        )
        return txn, attempt

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_success_email_uses_correct_template(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()

        send_payout_success_email(plan=self.plan, transaction=txn, attempt=attempt)

        self.assertEqual(mock_send.call_count, 1)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs['template_path'], 'payplan/nomba_payouts/payout_success.html')
        self.assertEqual(kwargs['recipient'], 'creator@example.com')

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_success_email_includes_plan_and_amount_in_context(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()

        send_payout_success_email(plan=self.plan, transaction=txn, attempt=attempt)

        ctx = mock_send.call_args.kwargs['context']
        self.assertEqual(ctx['plan_title'], "Lagos Apartment")
        self.assertEqual(ctx['amount'], "50,000.00")
        self.assertEqual(ctx['currency'], "NGN")
        self.assertEqual(ctx['cycle_number'], 1)
        self.assertEqual(ctx['payout_reference'], "PAYOUT_ABC")

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_failure_email_uses_correct_template(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()

        send_payout_failure_email(
            plan=self.plan,
            transaction=txn,
            attempt=attempt,
            reason="Account not found",
        )

        self.assertEqual(mock_send.call_count, 1)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs['template_path'], 'payplan/nomba_payouts/payout_failure.html')
        self.assertEqual(kwargs['recipient'], 'creator@example.com')

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_failure_email_includes_failure_reason(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()

        send_payout_failure_email(
            plan=self.plan,
            transaction=txn,
            attempt=attempt,
            reason="Bank rejected transfer",
        )

        ctx = mock_send.call_args.kwargs['context']
        self.assertEqual(ctx['failure_reason'], "Bank rejected transfer")
        self.assertEqual(ctx['plan_title'], "Lagos Apartment")
        self.assertEqual(ctx['amount'], "50,000.00")

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_success_email_context_includes_brand_chrome(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()
        send_payout_success_email(plan=self.plan, transaction=txn, attempt=attempt)
        ctx = mock_send.call_args.kwargs['context']
        self.assertIn('frontend_url', ctx)
        self.assertIn('year', ctx)

    @patch('payplan.nomba_payouts.emails.send_html_email')
    def test_failure_email_context_includes_brand_chrome(self, mock_send):
        txn, attempt = self._make_transaction_and_attempt()
        send_payout_failure_email(
            plan=self.plan, transaction=txn, attempt=attempt, reason="x"
        )
        ctx = mock_send.call_args.kwargs['context']
        self.assertIn('frontend_url', ctx)
        self.assertIn('year', ctx)

    @override_settings(BASE_URL="https://app.payplan.test/")
    def test_success_template_renders_with_brand_chrome(self):
        rendered = render_to_string(
            "payplan/nomba_payouts/payout_success.html",
            context={
                "plan_title": "Lagos Apartment",
                "amount": "50,000.00",
                "currency": "NGN",
                "cycle_number": 1,
                "payout_reference": "PAYOUT_ABC",
                "frontend_url": "https://app.payplan.test/",
                "year": 2026,
            },
        )
        self.assertIn("PayPlan", rendered)
        self.assertIn("Pay<span>Plan</span>", rendered)
        self.assertIn("https://app.payplan.test/", rendered)
        self.assertIn("Lagos Apartment", rendered)

    @override_settings(BASE_URL="https://app.payplan.test/")
    def test_failure_template_renders_with_brand_chrome(self):
        rendered = render_to_string(
            "payplan/nomba_payouts/payout_failure.html",
            context={
                "plan_title": "Lagos Apartment",
                "amount": "50,000.00",
                "currency": "NGN",
                "cycle_number": 1,
                "payout_reference": "PAYOUT_ABC",
                "failure_reason": "Bank rejected transfer",
                "frontend_url": "https://app.payplan.test/",
                "year": 2026,
            },
        )
        self.assertIn("PayPlan", rendered)
        self.assertIn("Pay<span>Plan</span>", rendered)
        self.assertIn("https://app.payplan.test/", rendered)
        self.assertIn("Bank rejected transfer", rendered)
