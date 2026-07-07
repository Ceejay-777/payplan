from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone


def map_proration_mode_to_sub_api(proration_mode, start_date, billing_date=None):
    today = timezone.now()

    if proration_mode == 'next_cycle':
        return {
            'start_date': (billing_date or start_date).isoformat(),
            'proration_behavior': 'none',
        }
    elif proration_mode == 'pro-rated':
        return {
            'start_date': today.isoformat(),
            'proration_behavior': 'prorate',
        }
    elif proration_mode == 'full_cycle':
        return {
            'start_date': today.isoformat(),
            'proration_behavior': 'charge_full',
        }


def calculate_first_charge_amount(amount, frequency, cohort_start_date, proration_mode):
    if proration_mode in ('next_cycle', 'full_cycle'):
        return float(amount)

    today = timezone.now().date()

    if isinstance(cohort_start_date, str):
        from django.utils.dateparse import parse_datetime
        cohort_start_date = parse_datetime(cohort_start_date)
    if cohort_start_date is None:
        return float(amount)

    start = cohort_start_date.date() if hasattr(cohort_start_date, 'date') else cohort_start_date

    period_start = _find_current_period_start(start, today, frequency)
    next_billing = _add_cycle(period_start, frequency)

    days_in_cycle = (next_billing - period_start).days
    days_remaining = (next_billing - today).days

    if days_in_cycle <= 0 or days_remaining <= 0:
        return float(amount)

    prorated = float(amount) * (days_remaining / days_in_cycle)
    return round(prorated, 2)


def _find_current_period_start(start, today, frequency):
    period_start = start
    next_period = _add_cycle(period_start, frequency)
    while next_period <= today:
        period_start = next_period
        next_period = _add_cycle(period_start, frequency)
    return period_start


def _add_cycle(date, frequency):
    if frequency == 'DAILY':
        return date + timedelta(days=1)
    elif frequency == 'WEEKLY':
        return date + timedelta(weeks=1)
    elif frequency == 'MONTHLY':
        return date + relativedelta(months=1)
    elif frequency == 'ANNUAL':
        return date + relativedelta(years=1)
    return date + timedelta(days=30)
