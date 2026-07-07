from datetime import datetime
from django.test import TestCase
from django.utils import timezone
from cohorts.proration_service import (
    map_proration_mode_to_sub_api, calculate_first_charge_amount,
)


class TestMapProrationMode(TestCase):
    def test_next_cycle_uses_billing_date(self):
        result = map_proration_mode_to_sub_api('next_cycle', datetime(2026, 1, 1), datetime(2026, 1, 15))
        self.assertEqual(result['proration_behavior'], 'none')
        self.assertIn('2026-01-15', result['start_date'])

    def test_pro_rated_uses_today(self):
        result = map_proration_mode_to_sub_api('pro-rated', datetime(2026, 1, 1))
        self.assertEqual(result['proration_behavior'], 'prorate')
        today_str = timezone.now().isoformat()[:10]
        self.assertIn(today_str, result['start_date'])

    def test_full_cycle_uses_today(self):
        result = map_proration_mode_to_sub_api('full_cycle', datetime(2026, 1, 1))
        self.assertEqual(result['proration_behavior'], 'charge_full')
        today_str = timezone.now().isoformat()[:10]
        self.assertIn(today_str, result['start_date'])

    def test_next_cycle_falls_back_to_start_date(self):
        result = map_proration_mode_to_sub_api('next_cycle', datetime(2026, 1, 1))
        self.assertIn('2026-01-01', result['start_date'])


class TestCalculateFirstCharge(TestCase):
    def test_next_cycle_returns_full_amount(self):
        result = calculate_first_charge_amount(100.00, 'MONTHLY', datetime(2026, 1, 1), 'next_cycle')
        self.assertEqual(result, 100.00)

    def test_full_cycle_returns_full_amount(self):
        result = calculate_first_charge_amount(100.00, 'MONTHLY', datetime(2026, 1, 1), 'full_cycle')
        self.assertEqual(result, 100.00)

    def test_pro_rated_returns_prorated_amount(self):
        result = calculate_first_charge_amount(100.00, 'MONTHLY', datetime(2026, 1, 1), 'pro-rated')
        self.assertGreater(result, 0)
        self.assertLess(result, 100.00)

    def test_pro_rated_for_daily_frequency(self):
        result = calculate_first_charge_amount(50.00, 'DAILY', datetime(2026, 1, 1), 'pro-rated')
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 50.00)
