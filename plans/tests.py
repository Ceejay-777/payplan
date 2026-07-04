from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from unittest.mock import patch
from .models import PayPlan
from .factories import PayPlanFactory, UserFactory
from .services import create_self_funded_plan, initialize_link_funded_plan, activate_plan

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

    def test_payplan_draft_without_creator_guard(self):
        # This test should verify the model level constraint
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
