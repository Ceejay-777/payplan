from django.test import TestCase, override_settings, Client
from django.core.exceptions import ValidationError
from django.utils import timezone
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from .models import PayPlan
from .factories import PayPlanFactory, UserFactory
from .services import (
    create_self_funded_plan, initialize_link_funded_plan, activate_plan, 
    update_plan_for_charge, resolve_and_cache_bank_account, use_bank_resolution,
    resolve_link_funded_plan
)

class TestPlans(TestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch('plans.services.create_sub_engine_plan')
    @patch('plans.services.create_subscription')
    @patch('plans.services.create_customer')
    @patch('plans.services.use_bank_resolution')
    def test_create_self_funded_plan_happy_path(self, mock_use_bank, mock_create_customer, mock_create_subscription, mock_create_sub_engine_plan):
        mock_use_bank.return_value = {
            "account_number": "1234567890",
            "bank_code": "011",
            "account_name": "Test Receiver"
        }
        mock_create_customer.return_value = "cust_123"
        mock_create_sub_engine_plan.return_value = "plan_123"
        mock_create_subscription.return_value = {"id": "sub_123", "checkout_link": "http://link.com"}

        validated_data = {
            "title": "Test Plan",
            "amount": 100.00,
            "frequency": PayPlan.Frequency.MONTHLY,
            "resolution_token": "token123"
        }
        
        plan, link = create_self_funded_plan(self.user, validated_data)
        
        self.assertEqual(plan.status, PayPlan.Status.AWAITING_FUNDING)
        self.assertEqual(plan.creator, self.user)
        self.assertEqual(plan.subscription_engine_id, "sub_123")
        self.assertEqual(link, "http://link.com")

    @patch('plans.services.create_customer')
    @patch('plans.services.use_bank_resolution')
    def test_create_self_funded_plan_idempotent_customer(self, mock_use_bank, mock_create_customer):
        mock_use_bank.return_value = {
            "account_number": "1234567890",
            "bank_code": "011",
            "account_name": "Test Receiver"
        }
        self.user.sub_engine_customer_id = "existing_cust"
        self.user.save()
        
        validated_data = {
            "title": "Test Plan",
            "amount": 100.00,
            "frequency": PayPlan.Frequency.MONTHLY,
            "resolution_token": "token123"
        }
        
        with patch('plans.services.create_sub_engine_plan'), patch('plans.services.create_subscription'):
            create_self_funded_plan(self.user, validated_data)
            
        mock_create_customer.assert_not_called()

    def test_payplan_draft_without_creator_guard(self):
        plan = PayPlanFactory.build(status=PayPlan.Status.ACTIVE, creator=None)
        with self.assertRaises(ValidationError):
            plan.save()
            
    @patch('plans.services.use_bank_resolution')
    def test_initialize_link_funded_plan(self, mock_use_bank):
        mock_use_bank.return_value = {
            "account_number": "1234567890",
            "bank_code": "011",
            "account_name": "Test Receiver"
        }
        
        data = {
            "title": "Link Plan",
            "amount": 50.00,
            "frequency": PayPlan.Frequency.DAILY,
            "resolution_token": "token123"
        }
        
        plan, link = initialize_link_funded_plan(data)
        
        self.assertEqual(plan.status, PayPlan.Status.DRAFT)
        self.assertTrue(plan.payment_link_token)
        self.assertIn("plt=", link)

    @patch('plans.services.create_sub_engine_plan')
    @patch('plans.services.create_subscription')
    @patch('plans.services.create_customer')
    def test_resolve_link_funded_plan(self, mock_create_customer, mock_create_subscription, mock_create_sub_engine_plan):
        plan = PayPlanFactory(status=PayPlan.Status.DRAFT)
        mock_create_customer.return_value = "new_cust"
        mock_create_sub_engine_plan.return_value = "plan_123"
        mock_create_subscription.return_value = {"id": "sub_123", "checkout_link": "http://link.com"}
        
        plan, link = resolve_link_funded_plan(plan, "guest@example.com")
        
        self.assertEqual(plan.status, PayPlan.Status.AWAITING_FUNDING)
        self.assertEqual(plan.creator.email, "guest@example.com")
        self.assertEqual(plan.creator.role, 'GUEST')
        self.assertEqual(plan.subscription_engine_id, "sub_123")

    def test_activate_plan(self):
        plan = PayPlanFactory(status=PayPlan.Status.AWAITING_FUNDING)
        engine_data = {
            "started_at": timezone.now(),
            "subscription_id": "engine_sub_1",
            "next_billing_date": timezone.now() + timezone.timedelta(days=30),
            "card_last_four": "4242",
            "card_type": "visa"
        }
        
        activate_plan(plan, engine_data)
        
        plan.refresh_from_db()
        self.assertEqual(plan.status, PayPlan.Status.ACTIVE)
        self.assertEqual(plan.engine_subscription_id, "engine_sub_1")

    def test_update_plan_for_charge(self):
        plan = PayPlanFactory(billing_count=0)
        engine_data = {"next_billing_date": timezone.now() + timezone.timedelta(days=30)}
        
        update_plan_for_charge(plan, engine_data)
        
        plan.refresh_from_db()
        self.assertEqual(plan.billing_count, 1)

    @patch('plans.services.resolve_bank_account')
    def test_resolve_and_cache_bank_account(self, mock_resolve):
        mock_resolve.return_value = "Test Account"
        resolution_data = {'account_number': '123', 'bank_code': '011'}
        
        result = resolve_and_cache_bank_account(resolution_data)
        
        self.assertIn('resolution_token', result)
        self.assertEqual(result['account_name'], "Test Account")
        
        # Verify cached
        self.assertIsNotNone(cache.get(f"bank_resolution-{result['resolution_token']}"))

    def test_use_bank_resolution_invalid(self):
        with self.assertRaises(ValidationError):
            use_bank_resolution("invalid_token")
