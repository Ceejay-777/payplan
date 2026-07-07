from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from plans.factories import UserFactory, PayPlanFactory
from plans.models import PayPlan
from cohorts.models import Cohort, CohortMembership


class TestResolutionLinkCohortContext(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()

    def test_cohort_resolution_link_includes_cohort_id(self):
        from cohorts.services import create_cohort
        cohort, payers = create_cohort(
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
        link = payers[0]['resolution_link']
        self.assertIn('&c=', link)
        self.assertIn(cohort.sqid, link)

    def test_non_cohort_plan_link_has_no_cohort_id(self):
        from plans.services import initialize_link_funded_plan, use_bank_resolution
        from unittest.mock import patch
        with patch('plans.services.use_bank_resolution') as mock_resolve:
            mock_resolve.return_value = {
                'account_name': 'John',
                'account_number': '1234567890',
                'bank_code': '011',
            }
            plan, link = initialize_link_funded_plan({
                'title': 'Test Plan',
                'amount': 100.00,
                'frequency': 'MONTHLY',
                'receiver_name': 'John',
                'resolution_token': 'fake_token',
            })
        self.assertNotIn('&c=', link)


class TestPlanDetailsEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()

    def test_returns_plan_details_for_valid_link(self):
        plan = PayPlanFactory(
            title='Test Plan',
            amount=100.00,
            status=PayPlan.Status.DRAFT,
        )
        response = self.client.get(
            reverse('plan-link-details'),
            {'p': plan.sqid, 'plt': plan.payment_link_token},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['title'], 'Test Plan')
        self.assertEqual(data['amount'], '100.00')

    def test_returns_cohort_context_for_cohort_plan(self):
        from cohorts.services import create_cohort
        cohort, payers = create_cohort(
            self.user,
            {
                'name': 'Cohort Name',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'receiver_account_name': 'John',
                'receiver_account_number': '1',
                'receiver_bank_code': '011',
            },
            payers=[{'title': 'Payer', 'amount': 100.00, 'metadata': {}}],
        )
        plan = payers[0]['plan']
        response = self.client.get(
            reverse('plan-link-details'),
            {'p': plan.sqid, 'plt': plan.payment_link_token},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['cohort_name'], 'Cohort Name')
        self.assertEqual(data['cohort_visibility'], 'closed')

    def test_rejects_expired_link(self):
        from django.utils import timezone
        from datetime import timedelta
        plan = PayPlanFactory(
            title='Expired',
            amount=100.00,
            status=PayPlan.Status.DRAFT,
        )
        PayPlan.objects.filter(pk=plan.pk).update(
            payment_link_expires_at=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(
            reverse('plan-link-details'),
            {'p': plan.sqid, 'plt': plan.payment_link_token},
        )
        self.assertEqual(response.status_code, 410)

    def test_returns_404_for_invalid_token(self):
        plan = PayPlanFactory(
            title='Test',
            amount=100.00,
            status=PayPlan.Status.DRAFT,
        )
        response = self.client.get(
            reverse('plan-link-details'),
            {'p': plan.sqid, 'plt': 'wrong_token'},
        )
        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_nonexistent_plan(self):
        response = self.client.get(
            reverse('plan-link-details'),
            {'p': 'nonexistent', 'plt': 'token'},
        )
        self.assertEqual(response.status_code, 404)

    def test_requires_both_params(self):
        response = self.client.get(reverse('plan-link-details'), {'p': 'abc'})
        self.assertEqual(response.status_code, 400)
