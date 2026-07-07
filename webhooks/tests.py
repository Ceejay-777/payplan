import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from cohorts.models import Cohort, CohortMembership
from cohorts.services import create_cohort
from plans.factories import PayPlanFactory, UserFactory
from plans.models import PayPlan
from transactions.models import Transaction, TransactionEvent
from webhooks.webhookshandlers import handle_billing_failed, handle_billing_success, handle_subscription_activated


class TestHandleBillingSuccessNoPayout(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(creator=self.user, status=PayPlan.Status.ACTIVE)

    def test_creates_transaction_and_updates_plan(self):
        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_001",
            "next_billing_date": "2026-08-05T00:00:00Z",
        })

        txn = Transaction.objects.get(plan=self.plan, billing_cycle_number=1)
        self.assertEqual(txn.status, Transaction.Status.CHARGE_SUCCESS)
        self.assertEqual(txn.charge_reference, "charge_ref_001")

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.billing_count, 1)

    def test_does_not_create_dunning_attempt(self):
        from transactions.models import Transaction as TxnModel
        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_002",
            "next_billing_date": "2026-08-05T00:00:00Z",
        })

        txn = TxnModel.objects.get(plan=self.plan, billing_cycle_number=1)
        self.assertFalse(hasattr(txn, 'dunning_attempts'))

    def test_is_idempotent(self):
        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_003",
            "next_billing_date": "2026-08-05T00:00:00Z",
        })

        txn_count = Transaction.objects.filter(plan=self.plan).count()
        self.assertEqual(txn_count, 1)

        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_003",
            "next_billing_date": "2026-08-05T00:00:00Z",
        })

        txn_count = Transaction.objects.filter(plan=self.plan).count()
        self.assertEqual(txn_count, 1)

    def test_billing_count_increments(self):
        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_004",
            "next_billing_date": "2026-08-05T00:00:00Z",
        })
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.billing_count, 1)

        handle_billing_success({
            "subscription_id": self.plan.engine_subscription_id,
            "reference": "charge_ref_005",
            "next_billing_date": "2026-09-05T00:00:00Z",
        })
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.billing_count, 2)


class TestSubscriptionActivatedCohortMembership(TestCase):
    def setUp(self):
        self.organizer = UserFactory()
        self.payer = UserFactory()

        validated_data = {
            'name': 'Test Cohort',
            'frequency': Cohort.Frequency.MONTHLY,
            'start_date': timezone.now(),
            'receiver_account_name': 'Test Account',
            'receiver_account_number': '1234567890',
            'receiver_bank_code': '001',
        }

        payers = [{
            'email': self.payer.email,
            'amount': 5000,
            'name': 'Test Payer',
        }]

        self.cohort, results = create_cohort(self.organizer, validated_data, payers)
        self.plan = results[0]['plan']
        self.membership = results[0]['membership']

        PayPlan.objects.filter(pk=self.plan.pk).update(
            engine_subscription_id='sub_cohort_001',
            creator=self.payer,
        )
        self.plan.refresh_from_db()

    def test_activates_plan_and_updates_cohort_membership(self):
        handle_subscription_activated({
            'subscription_id': 'sub_cohort_001',
            'started_at': '2026-01-01T00:00:00Z',
            'next_billing_date': '2026-02-01T00:00:00Z',
            'card_last_four': '1234',
            'card_type': 'VISA',
        })

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, PayPlan.Status.ACTIVE)

        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, CohortMembership.Status.ACTIVE)
        self.assertIsNotNone(self.membership.joined_at)


class TestSubscriptionActivatedNoCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(
            creator=self.user,
            status=PayPlan.Status.DRAFT,
            engine_subscription_id='sub_no_cohort_001',
        )

    def test_activates_plan_without_cohort_membership(self):
        handle_subscription_activated({
            'subscription_id': 'sub_no_cohort_001',
            'started_at': '2026-01-01T00:00:00Z',
            'next_billing_date': '2026-02-01T00:00:00Z',
            'card_last_four': '1234',
            'card_type': 'VISA',
        })

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, PayPlan.Status.ACTIVE)
        self.assertFalse(hasattr(self.plan, 'cohort_membership'))


class TestBillingFailedCohortMembership(TestCase):
    def setUp(self):
        self.organizer = UserFactory()
        self.payer = UserFactory()

        validated_data = {
            'name': 'Test Cohort Billing',
            'frequency': Cohort.Frequency.MONTHLY,
            'start_date': timezone.now(),
            'receiver_account_name': 'Test Account',
            'receiver_account_number': '0987654321',
            'receiver_bank_code': '002',
        }

        payers = [{
            'email': self.payer.email,
            'amount': 7500,
            'name': 'Test Payer',
        }]

        self.cohort, results = create_cohort(self.organizer, validated_data, payers)
        self.plan = results[0]['plan']
        self.membership = results[0]['membership']

        PayPlan.objects.filter(pk=self.plan.pk).update(
            status=PayPlan.Status.ACTIVE,
            engine_subscription_id='sub_fail_001',
            creator=self.payer,
        )
        self.plan.refresh_from_db()

    def test_records_failed_transaction_and_updates_membership(self):
        handle_billing_failed({
            'subscription_id': 'sub_fail_001',
            'reference': 'charge_fail_ref_001',
            'reason': 'Insufficient funds',
        })

        txn = Transaction.objects.get(plan=self.plan)
        self.assertEqual(txn.status, Transaction.Status.CHARGE_FAILED)
        self.assertEqual(txn.charge_reference, 'charge_fail_ref_001')

        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, CohortMembership.Status.FAILED)


class TestBillingFailedNoCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = PayPlanFactory(
            creator=self.user,
            status=PayPlan.Status.ACTIVE,
            engine_subscription_id='sub_fail_no_cohort_001',
        )

    def test_records_failed_transaction_without_cohort(self):
        handle_billing_failed({
            'subscription_id': 'sub_fail_no_cohort_001',
            'reference': 'charge_fail_ref_002',
            'reason': 'Card declined',
        })

        txn = Transaction.objects.get(plan=self.plan)
        self.assertEqual(txn.status, Transaction.Status.CHARGE_FAILED)
        self.assertEqual(txn.charge_reference, 'charge_fail_ref_002')
        self.assertFalse(hasattr(self.plan, 'cohort_membership'))
