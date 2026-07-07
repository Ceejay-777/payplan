from django.test import TestCase
from unittest.mock import patch

from decimal import Decimal

from plans.factories import PayPlanFactory, UserFactory
from plans.models import PayPlan
from transactions.models import Transaction
from cohorts.models import Cohort, CohortMembership
from cohorts.services import (
    create_cohort, add_payers_to_cohort, remove_payer_from_cohort,
    update_cohort, get_cohort_summary, get_cohort_transactions,
    batch_pause_plans, batch_resume_plans, batch_retry_plans,
)


class TestCreateCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_creates_cohort_without_payers(self):
        cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
        )
        self.assertEqual(cohort.name, 'Test Cohort')
        self.assertEqual(cohort.organizer, self.user)
        self.assertEqual(payers, [])

    def test_creates_cohort_with_payers(self):
        cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
            ],
        )
        self.assertEqual(len(payers), 2)
        for r in payers:
            plan = r['plan']
            self.assertEqual(plan.receiver_account_name, 'John Doe')
            self.assertEqual(plan.receiver_account_number, '1234567890')
            self.assertEqual(plan.receiver_bank_code, '011')
            self.assertEqual(plan.cohort_id, cohort.sqid)
            self.assertEqual(plan.status, PayPlan.Status.DRAFT)
            self.assertIn('resolution_link', r)
            self.assertIn('&c=', r['resolution_link'])

    def test_payer_plan_has_correct_amount(self):
        cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer One', 'amount': 150.00, 'metadata': {}}],
        )
        self.assertEqual(payers[0]['plan'].amount, 150.00)


class TestAddPayersToCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, _ = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
        )

    def test_adds_payers_to_existing_cohort(self):
        payers = add_payers_to_cohort(
            self.cohort,
            [{'title': 'New Payer', 'amount': 300.00, 'metadata': {}}],
        )
        self.assertEqual(len(payers), 1)
        plan = payers[0]['plan']
        self.assertEqual(plan.receiver_account_name, 'John Doe')
        self.assertEqual(plan.cohort_id, self.cohort.sqid)

    def test_multiple_payers_added(self):
        payers = add_payers_to_cohort(
            self.cohort,
            [
                {'title': 'Payer A', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer B', 'amount': 200.00, 'metadata': {}},
                {'title': 'Payer C', 'amount': 300.00, 'metadata': {}},
            ],
        )
        self.assertEqual(len(payers), 3)
        self.assertEqual(CohortMembership.objects.filter(cohort=self.cohort).count(), 3)


class TestRemovePayerFromCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer One', 'amount': 100.00, 'metadata': {}}],
        )
        self.plan = payers[0]['plan']
        self.membership = payers[0]['membership']

    def test_removes_payer_and_cancels_plan(self):
        remove_payer_from_cohort(self.cohort, self.plan)
        self.membership.refresh_from_db()
        self.plan.refresh_from_db()
        self.assertEqual(self.membership.status, CohortMembership.Status.CANCELLED)
        self.assertEqual(self.plan.status, PayPlan.Status.CANCELLED)


class TestUpdateCohort(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, _ = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
        )

    def test_updates_cohort_fields(self):
        updated = update_cohort(self.cohort, {'name': 'Updated Name', 'description': 'New description'})
        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.description, 'New description')

    def test_bank_details_change_does_not_affect_existing_plans(self):
        plan = PayPlanFactory(creator=self.user)
        CohortMembership.objects.create(cohort=self.cohort, plan=plan, amount=100.00)
        update_cohort(self.cohort, {
            'receiver_account_name': 'Jane Doe',
            'receiver_account_number': '0987654321',
            'receiver_bank_code': '058',
        })
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.receiver_account_name, 'Jane Doe')
        plan.refresh_from_db()
        self.assertEqual(plan.receiver_account_name, 'Test Receiver')


class TestCohortSummary(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
                {'title': 'Payer Three', 'amount': 300.00, 'metadata': {}},
            ],
        )
        self.payers = payers

    def test_summary_returns_baseline(self):
        summary = get_cohort_summary(self.cohort)
        self.assertEqual(summary['total_expected'], 600.00)
        self.assertEqual(summary['total_collected'], 0)
        self.assertEqual(summary['total_payers'], 3)
        self.assertEqual(summary['active_payers'], 0)
        self.assertEqual(summary['collection_percentage'], 0)

    def test_summary_reflects_active_memberships(self):
        membership = self.payers[0]['membership']
        membership.status = CohortMembership.Status.ACTIVE
        membership.save(update_fields=['status'])
        summary = get_cohort_summary(self.cohort)
        self.assertEqual(summary['active_payers'], 1)


class TestGetCohortTransactions(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer One', 'amount': 100.00, 'metadata': {}}],
        )
        self.plan = payers[0]['plan']

    def test_returns_empty_when_no_transactions(self):
        qs = get_cohort_transactions(self.cohort)
        self.assertEqual(len(qs), 0)

    def test_returns_transactions_for_cohort_plans(self):
        Transaction.objects.create(
            plan=self.plan, amount=Decimal('100.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
        )
        qs = get_cohort_transactions(self.cohort)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].amount, Decimal('100.00'))

    def test_filters_by_start_date(self):
        Transaction.objects.create(
            plan=self.plan, amount=Decimal('50.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
            charged_at='2026-01-01T12:00:00Z',
        )
        qs = get_cohort_transactions(self.cohort, start_date='2026-01-02T00:00:00Z')
        self.assertEqual(len(qs), 0)

    def test_filters_by_end_date(self):
        Transaction.objects.create(
            plan=self.plan, amount=Decimal('50.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
            charged_at='2026-01-01T12:00:00Z',
        )
        qs = get_cohort_transactions(self.cohort, end_date='2026-01-01T00:00:00Z')
        self.assertEqual(len(qs), 0)

    def test_does_not_include_other_cohort_transactions(self):
        other_cohort, _ = create_cohort(
            self.user,
            {
                'name': 'Other Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-02-01T00:00:00Z',
                'receiver_account_name': 'Jane Doe',
                'receiver_account_number': '0987654321',
                'receiver_bank_code': '058',
            },
            payers=[{'title': 'Other Payer', 'amount': 200.00, 'metadata': {}}],
        )
        other_plan = other_cohort.memberships.first().plan
        Transaction.objects.create(
            plan=other_plan, amount=Decimal('200.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
        )
        qs = get_cohort_transactions(self.cohort)
        self.assertEqual(len(qs), 0)


class TestBatchPause(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
            ],
        )
        self.plan1 = payers[0]['plan']
        self.plan2 = payers[1]['plan']
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.ACTIVE)
        PayPlan.objects.filter(pk=self.plan2.pk).update(status=PayPlan.Status.ACTIVE)
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.ACTIVE)

    def test_pauses_all_plans(self):
        result = batch_pause_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 2)
        self.assertEqual(result['failed'], 0)
        self.plan1.refresh_from_db()
        self.plan2.refresh_from_db()
        self.assertEqual(self.plan1.status, PayPlan.Status.PAUSED)
        self.assertEqual(self.plan2.status, PayPlan.Status.PAUSED)
        ms = CohortMembership.objects.filter(cohort=self.cohort)
        self.assertEqual(ms.filter(status=CohortMembership.Status.PAUSED).count(), 2)

    def test_pause_by_membership_ids(self):
        m1 = CohortMembership.objects.get(cohort=self.cohort, plan=self.plan1)
        result = batch_pause_plans(self.cohort, membership_ids=[m1.sqid])
        self.assertEqual(result['succeeded'], 1)
        self.plan1.refresh_from_db()
        self.assertEqual(self.plan1.status, PayPlan.Status.PAUSED)

    def test_pause_already_paused_plan_fails(self):
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.PAUSED)
        result = batch_pause_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 1)
        self.assertEqual(result['failed'], 1)

    def test_pause_empty_list_returns_zero(self):
        result = batch_pause_plans(self.cohort, plan_ids=[])
        self.assertEqual(result['total'], 0)

    def test_pause_missing_id_reported(self):
        result = batch_pause_plans(self.cohort, plan_ids=['nonexistent'])
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['details'][0]['error'], 'Not found in cohort')


class TestBatchResume(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
            ],
        )
        self.plan1 = payers[0]['plan']
        self.plan2 = payers[1]['plan']
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.PAUSED)
        PayPlan.objects.filter(pk=self.plan2.pk).update(status=PayPlan.Status.PAUSED)
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.PAUSED)

    def test_resumes_all_plans(self):
        result = batch_resume_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 2)
        self.plan1.refresh_from_db()
        self.assertEqual(self.plan1.status, PayPlan.Status.ACTIVE)
        ms = CohortMembership.objects.get(cohort=self.cohort, plan=self.plan1)
        self.assertEqual(ms.status, CohortMembership.Status.ACTIVE)

    def test_resume_active_plan_fails(self):
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.ACTIVE)
        result = batch_resume_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 1)
        self.assertEqual(result['failed'], 1)

    def test_resume_empty_list(self):
        result = batch_resume_plans(self.cohort, plan_ids=[])
        self.assertEqual(result['total'], 0)


class TestBatchRetry(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': Cohort.Frequency.MONTHLY,
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John Doe',
                'receiver_account_number': '1234567890',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
            ],
        )
        self.plan1 = payers[0]['plan']
        self.plan2 = payers[1]['plan']
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.ACTIVE)
        PayPlan.objects.filter(pk=self.plan2.pk).update(status=PayPlan.Status.ACTIVE)
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.FAILED)

    def test_retries_failed_memberships(self):
        result = batch_retry_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 2)
        ms = CohortMembership.objects.get(cohort=self.cohort, plan=self.plan1)
        self.assertEqual(ms.status, CohortMembership.Status.ACTIVE)

    def test_retry_non_failed_membership_fails(self):
        CohortMembership.objects.filter(cohort=self.cohort, plan=self.plan1).update(status=CohortMembership.Status.ACTIVE)
        result = batch_retry_plans(self.cohort, plan_ids=[self.plan1.sqid, self.plan2.sqid])
        self.assertEqual(result['succeeded'], 1)
        self.assertEqual(result['failed'], 1)

    def test_retry_empty_list(self):
        result = batch_retry_plans(self.cohort, plan_ids=[])
        self.assertEqual(result['total'], 0)
