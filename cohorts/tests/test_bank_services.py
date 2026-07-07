from unittest.mock import patch
from django.test import TestCase
from plans.factories import UserFactory
from cohorts.models import SavedBankAccount
from cohorts.bank_services import save_bank_account, update_bank_account, delete_bank_account, resolve_bank_account


class TestSaveBankAccount(TestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch('cohorts.bank_services.nomba_resolve')
    def test_saves_bank_account_with_resolved_name(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        account = save_bank_account(
            self.user, account_number='1234567890', bank_code='011',
            nickname='My Account',
        )
        self.assertEqual(account.account_name, 'John Doe')
        self.assertEqual(account.account_number, '1234567890')
        self.assertEqual(account.bank_code, '011')
        self.assertEqual(account.nickname, 'My Account')
        self.assertEqual(account.user, self.user)

    @patch('cohorts.bank_services.nomba_resolve')
    def test_sets_default_flag(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        account = save_bank_account(
            self.user, account_number='1234567890', bank_code='011',
            is_default=True,
        )
        self.assertTrue(account.is_default)

    @patch('cohorts.bank_services.nomba_resolve')
    def test_unsets_previous_default(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        first = save_bank_account(
            self.user, account_number='1111111111', bank_code='011',
            is_default=True,
        )
        second = save_bank_account(
            self.user, account_number='2222222222', bank_code='011',
            is_default=True,
        )
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    @patch('cohorts.bank_services.nomba_resolve')
    def test_enforces_unique_per_user_account_bank(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        save_bank_account(self.user, account_number='1234567890', bank_code='011')
        with self.assertRaises(Exception):
            save_bank_account(self.user, account_number='1234567890', bank_code='011')


class TestUpdateBankAccount(TestCase):
    def setUp(self):
        self.user = UserFactory()
        from cohorts.bank_services import save_bank_account as sba
        with patch('cohorts.bank_services.nomba_resolve', return_value='John Doe'):
            self.account = sba(self.user, account_number='1234567890', bank_code='011')

    def test_updates_nickname(self):
        updated = update_bank_account(self.account, {'nickname': 'New Name'})
        self.assertEqual(updated.nickname, 'New Name')

    def test_sets_default_and_unsets_old(self):
        with patch('cohorts.bank_services.nomba_resolve', return_value='Jane Doe'):
            other = save_bank_account(self.user, account_number='9999999999', bank_code='011', is_default=True)
        update_bank_account(self.account, {'is_default': True})
        self.account.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(self.account.is_default)
        self.assertFalse(other.is_default)


class TestDeleteBankAccount(TestCase):
    def setUp(self):
        self.user = UserFactory()
        with patch('cohorts.bank_services.nomba_resolve', return_value='John Doe'):
            from cohorts.bank_services import save_bank_account as sba
            self.account = sba(self.user, account_number='1234567890', bank_code='011')

    def test_soft_deletes(self):
        delete_bank_account(self.account)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, SavedBankAccount.Status.INACTIVE)


class TestResolveBankAccount(TestCase):
    @patch('cohorts.bank_services.nomba_resolve')
    def test_resolves_and_caches(self, mock_resolve):
        mock_resolve.return_value = 'John Doe'
        from django.core.cache import cache
        cache.clear()
        result = resolve_bank_account('1234567890', '011')
        self.assertEqual(result, 'John Doe')
        mock_resolve.assert_called_once_with('1234567890', '011')
        result2 = resolve_bank_account('1234567890', '011')
        self.assertEqual(result2, 'John Doe')
        mock_resolve.assert_called_once()
