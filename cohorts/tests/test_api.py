import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from plans.factories import UserFactory
from transactions.models import Transaction
from cohorts.models import Cohort


class BaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def _cohort_payload(self, **overrides):
        payload = {
            'name': 'Test Cohort',
            'frequency': 'MONTHLY',
            'interval_count': 1,
            'start_date': '2026-01-01T00:00:00Z',
            'receiver_account_name': 'John Doe',
            'receiver_account_number': '1234567890',
            'receiver_bank_code': '011',
        }
        payload.update(overrides)
        return payload


class TestCreateCohortAPI(BaseAPITest):
    def test_create_cohort_without_payers(self):
        response = self.client.post(
            reverse('cohort-list-create'),
            self._cohort_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(data['name'], 'Test Cohort')
        self.assertIn('sqid', data)

    def test_create_cohort_with_payers(self):
        payload = self._cohort_payload(payers=[
            {'name': 'Payer One', 'email': 'payer1@example.com', 'amount': '100.00', 'metadata': {}},
            {'name': 'Payer Two', 'email': 'payer2@example.com', 'amount': '200.00', 'metadata': {}},
        ])
        response = self.client.post(reverse('cohort-list-create'), payload, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertIn('payers', data)
        self.assertEqual(len(data['payers']), 2)
        for p in data['payers']:
            self.assertIn('resolution_link', p)
            self.assertIn('plan_sqid', p)

    def test_unauthenticated_user_cannot_create(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse('cohort-list-create'),
            self._cohort_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 401)


class TestListCohortsAPI(BaseAPITest):
    def test_lists_own_cohorts(self):
        Cohort.objects.create(
            organizer=self.user, name='Cohort 1',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='John', receiver_account_number='1', receiver_bank_code='011',
        )
        Cohort.objects.create(
            organizer=self.user, name='Cohort 2',
            frequency='WEEKLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='Jane', receiver_account_number='2', receiver_bank_code='058',
        )
        other_user = UserFactory()
        Cohort.objects.create(
            organizer=other_user, name='Not Mine',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='Other', receiver_account_number='3', receiver_bank_code='011',
        )
        response = self.client.get(reverse('cohort-list-create'))
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(len(data), 2)


class TestRetrieveCohortAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.cohort = Cohort.objects.create(
            organizer=self.user, name='My Cohort',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='John', receiver_account_number='1', receiver_bank_code='011',
        )

    def test_retrieve_own_cohort(self):
        response = self.client.get(reverse('retrieve-cohort', kwargs={'sqid': self.cohort.sqid}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['name'], 'My Cohort')

    def test_cannot_retrieve_other_users_cohort(self):
        other_user = UserFactory()
        other_cohort = Cohort.objects.create(
            organizer=other_user, name='Not Mine',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='Other', receiver_account_number='3', receiver_bank_code='011',
        )
        response = self.client.get(reverse('retrieve-cohort', kwargs={'sqid': other_cohort.sqid}))
        self.assertEqual(response.status_code, 404)


class TestUpdateCohortAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.cohort = Cohort.objects.create(
            organizer=self.user, name='Original Name',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='John', receiver_account_number='1', receiver_bank_code='011',
        )

    def test_update_cohort_name(self):
        response = self.client.patch(
            reverse('update-cohort', kwargs={'sqid': self.cohort.sqid}),
            {'name': 'Updated Name'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.name, 'Updated Name')

    def test_update_cohort_bank_details(self):
        response = self.client.patch(
            reverse('update-cohort', kwargs={'sqid': self.cohort.sqid}),
            {'receiver_account_name': 'Jane Doe', 'receiver_account_number': '9999999999'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.cohort.refresh_from_db()
        self.assertEqual(self.cohort.receiver_account_name, 'Jane Doe')
        self.assertEqual(self.cohort.receiver_account_number, '9999999999')


class TestDeleteCohortAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.cohort = Cohort.objects.create(
            organizer=self.user, name='To Delete',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='John', receiver_account_number='1', receiver_bank_code='011',
        )

    def test_delete_own_cohort(self):
        response = self.client.delete(
            reverse('delete-cohort', kwargs={'sqid': self.cohort.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        self.cohort.refresh_from_db()
        self.assertTrue(self.cohort.is_deleted)

    def test_cannot_delete_other_users_cohort(self):
        other_user = UserFactory()
        other_cohort = Cohort.objects.create(
            organizer=other_user, name='Not Mine',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='Other', receiver_account_number='3', receiver_bank_code='011',
        )
        response = self.client.delete(
            reverse('delete-cohort', kwargs={'sqid': other_cohort.sqid}),
        )
        self.assertEqual(response.status_code, 404)


class TestAddPayersToCohortAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.cohort = Cohort.objects.create(
            organizer=self.user, name='Test Cohort',
            frequency='MONTHLY', start_date='2026-01-01T00:00:00Z',
            receiver_account_name='John', receiver_account_number='1', receiver_bank_code='011',
        )

    def test_add_payers(self):
        response = self.client.post(
            reverse('cohort-payers', kwargs={'sqid': self.cohort.sqid}),
            {'payers': [
                {'name': 'New Payer', 'email': 'new@example.com', 'amount': '150.00', 'metadata': {}},
            ]},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(len(data['payers']), 1)
        self.assertIn('resolution_link', data['payers'][0])

    def test_add_multiple_payers(self):
        response = self.client.post(
            reverse('cohort-payers', kwargs={'sqid': self.cohort.sqid}),
            {'payers': [
                {'name': 'Payer A', 'email': 'a@example.com', 'amount': '100.00', 'metadata': {}},
                {'name': 'Payer B', 'email': 'b@example.com', 'amount': '200.00', 'metadata': {}},
            ]},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()['data']['payers']), 2)


class TestRemovePayerFromCohortAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        from cohorts.services import create_cohort
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer', 'amount': 100.00, 'metadata': {}}],
        )
        self.plan = payers[0]['plan']

    def test_remove_payer(self):
        response = self.client.delete(
            reverse('remove-payer', kwargs={'sqid': self.cohort.sqid, 'plan_sqid': self.plan.sqid}),
        )
        self.assertEqual(response.status_code, 200)

    def test_remove_payer_cancels_plan(self):
        self.client.delete(
            reverse('remove-payer', kwargs={'sqid': self.cohort.sqid, 'plan_sqid': self.plan.sqid}),
        )
        from plans.models import PayPlan
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, PayPlan.Status.CANCELLED)


class TestCohortSummaryAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        from cohorts.services import create_cohort
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'P1', 'amount': 100.00, 'metadata': {}},
                {'title': 'P2', 'amount': 200.00, 'metadata': {}},
            ],
        )

    def test_summary_endpoint(self):
        response = self.client.get(
            reverse('cohort-summary', kwargs={'sqid': self.cohort.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['total_expected'], '300.00')
        self.assertEqual(data['total_collected'], '0.00')
        self.assertEqual(data['total_payers'], 2)


class TestCohortListPayersAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        from cohorts.services import create_cohort
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer One', 'amount': 100.00, 'metadata': {}}],
        )

    def test_list_payers(self):
        response = self.client.get(
            reverse('cohort-payers', kwargs={'sqid': self.cohort.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(len(data), 1)


class TestCohortTransactionsAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        from cohorts.services import create_cohort
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer One', 'amount': 100.00, 'metadata': {}}],
        )
        self.plan = payers[0]['plan']

    def test_transactions_empty_when_none_exist(self):
        response = self.client.get(
            reverse('cohort-transactions', kwargs={'sqid': self.cohort.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)

    def test_returns_paginated_transactions(self):
        Transaction.objects.create(
            plan=self.plan, amount=Decimal('100.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
        )
        response = self.client.get(
            reverse('cohort-transactions', kwargs={'sqid': self.cohort.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['amount'], '100.00')

    def test_cannot_access_other_users_cohort_transactions(self):
        other_user = UserFactory()
        from cohorts.services import create_cohort as cc
        other_cohort, _ = cc(
            other_user,
            {
                'name': 'Not Mine',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'Other',
                'receiver_account_number': '2',
                'receiver_bank_code': '011',
            },
        )
        response = self.client.get(
            reverse('cohort-transactions', kwargs={'sqid': other_cohort.sqid}),
        )
        self.assertEqual(response.status_code, 404)

    def test_filters_by_date_range(self):
        Transaction.objects.create(
            plan=self.plan, amount=Decimal('100.00'),
            billing_cycle_number=1, status=Transaction.Status.CHARGE_SUCCESS,
            charged_at='2026-06-01T12:00:00Z',
        )
        response = self.client.get(
            reverse('cohort-transactions', kwargs={'sqid': self.cohort.sqid}),
            {'start_date': '2026-06-02T00:00:00Z'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)


class TestBatchActionsAPI(BaseAPITest):
    def setUp(self):
        super().setUp()
        from cohorts.services import create_cohort
        self.cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[
                {'title': 'Payer One', 'amount': 100.00, 'metadata': {}},
                {'title': 'Payer Two', 'amount': 200.00, 'metadata': {}},
            ],
        )
        self.plan1 = payers[0]['plan']
        self.plan2 = payers[1]['plan']
        from plans.models import PayPlan
        from cohorts.models import CohortMembership
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.ACTIVE)
        PayPlan.objects.filter(pk=self.plan2.pk).update(status=PayPlan.Status.ACTIVE)
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.ACTIVE)

    def test_batch_pause(self):
        response = self.client.post(
            reverse('cohort-batch-pause', kwargs={'sqid': self.cohort.sqid}),
            {'plan_ids': [self.plan1.sqid, self.plan2.sqid]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['succeeded'], 2)
        self.assertEqual(data['failed'], 0)

    def test_batch_resume(self):
        from plans.models import PayPlan
        from cohorts.models import CohortMembership
        PayPlan.objects.filter(pk=self.plan1.pk).update(status=PayPlan.Status.PAUSED)
        PayPlan.objects.filter(pk=self.plan2.pk).update(status=PayPlan.Status.PAUSED)
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.PAUSED)
        response = self.client.post(
            reverse('cohort-batch-resume', kwargs={'sqid': self.cohort.sqid}),
            {'plan_ids': [self.plan1.sqid, self.plan2.sqid]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['succeeded'], 2)

    def test_batch_retry(self):
        from cohorts.models import CohortMembership
        CohortMembership.objects.filter(cohort=self.cohort).update(status=CohortMembership.Status.FAILED)
        response = self.client.post(
            reverse('cohort-batch-retry', kwargs={'sqid': self.cohort.sqid}),
            {'plan_ids': [self.plan1.sqid, self.plan2.sqid]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['succeeded'], 2)

    def test_batch_pause_by_membership_ids(self):
        from cohorts.models import CohortMembership
        m1 = CohortMembership.objects.get(plan=self.plan1)
        response = self.client.post(
            reverse('cohort-batch-pause', kwargs={'sqid': self.cohort.sqid}),
            {'membership_ids': [m1.sqid]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['succeeded'], 1)

    def test_batch_action_both_ids_rejected(self):
        response = self.client.post(
            reverse('cohort-batch-pause', kwargs={'sqid': self.cohort.sqid}),
            {'plan_ids': ['x'], 'membership_ids': ['y']},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_batch_action_none_ids_rejected(self):
        response = self.client.post(
            reverse('cohort-batch-pause', kwargs={'sqid': self.cohort.sqid}),
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_batch_action_security_other_user_cohort(self):
        other_user = UserFactory()
        from cohorts.services import create_cohort as cc
        other_cohort, _ = cc(
            other_user,
            {
                'name': 'Not Mine',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'Other',
                'receiver_account_number': '2',
                'receiver_bank_code': '011',
            },
        )
        response = self.client.post(
            reverse('cohort-batch-pause', kwargs={'sqid': other_cohort.sqid}),
            {'plan_ids': ['x']},
            format='json',
        )
        self.assertEqual(response.status_code, 404)
