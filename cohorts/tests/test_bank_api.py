from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from plans.factories import UserFactory
from cohorts.models import SavedBankAccount


class BaseBankAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def _create_account(self, **kwargs):
        data = {
            'account_number': kwargs.get('account_number', '1234567890'),
            'bank_code': kwargs.get('bank_code', '011'),
            'account_name': kwargs.get('account_name', 'John Doe'),
            'bank_name': kwargs.get('bank_name', ''),
            'nickname': kwargs.get('nickname', ''),
            'is_default': kwargs.get('is_default', False),
            'user': self.user,
        }
        return SavedBankAccount.objects.create(**data)


class TestCreateBankAccountAPI(BaseBankAPITest):
    @patch('cohorts.bank_services.nomba_resolve')
    def test_creates_bank_account(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        response = self.client.post(
            reverse('bank-account-list-create'),
            {'account_number': '1234567890', 'bank_code': '011'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(data['account_name'], 'John Doe')
        self.assertEqual(data['account_number'], '1234567890')

    def test_unauthenticated_user_cannot_create(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse('bank-account-list-create'),
            {'account_number': '1234567890', 'bank_code': '011'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)


class TestListBankAccountsAPI(BaseBankAPITest):
    def test_lists_own_accounts(self):
        self._create_account(account_number='1111111111')
        self._create_account(account_number='2222222222')
        other_user = UserFactory()
        SavedBankAccount.objects.create(
            user=other_user, account_number='3333333333', bank_code='011',
            account_name='Other', bank_name='',
        )
        response = self.client.get(reverse('bank-account-list-create'))
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(len(data), 2)

    def test_excludes_inactive_accounts(self):
        self._create_account(account_number='1111111111')
        inactive = self._create_account(account_number='2222222222')
        inactive.status = SavedBankAccount.Status.INACTIVE
        inactive.save()
        response = self.client.get(reverse('bank-account-list-create'))
        self.assertEqual(len(response.json()['data']), 1)


class TestDeleteBankAccountAPI(BaseBankAPITest):
    def test_soft_deletes(self):
        account = self._create_account()
        response = self.client.delete(
            reverse('bank-account-delete', kwargs={'sqid': account.sqid}),
        )
        self.assertEqual(response.status_code, 200)
        account.refresh_from_db()
        self.assertEqual(account.status, SavedBankAccount.Status.INACTIVE)


class TestCohortCreationWithBankAccount(BaseBankAPITest):
    @patch('cohorts.bank_services.nomba_resolve')
    @patch('cohorts.plan_services.create_cohort_plan')
    def test_creates_cohort_with_bank_account(self, mock_create_plan, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        from cohorts.services import create_cohort
        account = self._create_account(
            account_number='1234567890', bank_code='011', account_name='John Doe',
        )
        cohort, _ = create_cohort(
            self.user,
            {
                'name': 'Test Cohort',
                'frequency': 'MONTHLY',
                'start_date': '2026-01-01T00:00:00Z',
                'bank_account_id': account.sqid,
            },
        )
        self.assertEqual(cohort.receiver_account_name, 'John Doe')
        self.assertEqual(cohort.receiver_account_number, '1234567890')
        self.assertEqual(cohort.receiver_bank_code, '011')
        self.assertEqual(cohort.saved_bank_account, account)
