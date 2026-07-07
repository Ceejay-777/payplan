from django.db import transaction
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404

from plans.models import PayPlan
from plans.services import cancel_plan
from transactions.models import Transaction
from .models import Cohort, CohortMembership, SavedBankAccount
from .plan_services import create_cohort_plan


def get_cohort_transactions(cohort, start_date=None, end_date=None):
    qs = Transaction.objects.filter(
        plan__cohort_membership__cohort=cohort,
    ).select_related('plan').order_by('-created_at')

    if start_date:
        qs = qs.filter(charged_at__gte=start_date)
    if end_date:
        qs = qs.filter(charged_at__lte=end_date)

    return qs


def create_cohort(organizer, validated_data, payers=None):
    bank_account_id = validated_data.pop('bank_account_id', None)

    if bank_account_id:
        bank_account = get_object_or_404(SavedBankAccount, sqid=bank_account_id, user=organizer)
        validated_data.setdefault('receiver_account_name', bank_account.account_name)
        validated_data.setdefault('receiver_account_number', bank_account.account_number)
        validated_data.setdefault('receiver_bank_code', bank_account.bank_code)
        validated_data['saved_bank_account'] = bank_account

    with transaction.atomic():
        cohort = Cohort.objects.create(organizer=organizer, **validated_data)
        cohort.refresh_from_db()

        payer_results = []
        if payers:
            for payer_data in payers:
                plan, membership, resolution_link = create_cohort_plan(cohort, payer_data)
                payer_results.append({
                    'plan': plan,
                    'membership': membership,
                    'resolution_link': resolution_link,
                })

    return cohort, payer_results


def add_payers_to_cohort(cohort, payers):
    with transaction.atomic():
        payer_results = []
        for payer_data in payers:
            plan, membership, resolution_link = create_cohort_plan(cohort, payer_data)
            payer_results.append({
                'plan': plan,
                'membership': membership,
                'resolution_link': resolution_link,
            })
    return payer_results


def remove_payer_from_cohort(cohort, plan):
    membership = get_object_or_404(CohortMembership, cohort=cohort, plan=plan)
    with transaction.atomic():
        membership.status = CohortMembership.Status.CANCELLED
        membership.save(update_fields=['status'])
        PayPlan.objects.filter(pk=plan.pk).update(status=PayPlan.Status.CANCELLED)
        plan.refresh_from_db()
    return membership


def update_cohort(cohort, validated_data):
    for attr, value in validated_data.items():
        setattr(cohort, attr, value)
    cohort.save(update_fields=validated_data.keys())
    cohort.refresh_from_db()
    return cohort


def get_cohort_summary(cohort):
    memberships = CohortMembership.objects.filter(cohort=cohort)
    plans = PayPlan.objects.filter(cohort_membership__cohort=cohort)
    plan_ids = plans.values_list('id', flat=True)

    total_expected = sum(m.amount for m in memberships)
    active_count = memberships.filter(status=CohortMembership.Status.ACTIVE).count()
    total_payers = memberships.count()

    collected = Transaction.objects.filter(
        plan_id__in=plan_ids,
        status=Transaction.Status.CHARGE_SUCCESS,
    ).aggregate(total=Sum('amount'))['total'] or 0

    collection_pct = round((collected / total_expected) * 100, 1) if total_expected else 0

    next_billing_date = plans.filter(
        next_billing_date__isnull=False
    ).order_by('next_billing_date').values_list('next_billing_date', flat=True).first()

    return {
        'total_expected': total_expected,
        'total_collected': collected,
        'collection_percentage': collection_pct,
        'active_payers': active_count,
        'total_payers': total_payers,
        'next_billing_date': next_billing_date,
    }


def _resolve_plans_and_missing(cohort, plan_ids=None, membership_ids=None):
    if plan_ids and membership_ids:
        raise ValueError("Provide either plan_ids or membership_ids, not both")

    if plan_ids:
        plans = list(
            PayPlan.objects.filter(
                sqid__in=plan_ids,
                cohort_membership__cohort=cohort,
            ).select_related('cohort_membership')
        )
        found = {p.sqid for p in plans}
        missing = [pid for pid in plan_ids if pid not in found]
        return plans, missing

    if membership_ids:
        memberships = list(
            CohortMembership.objects.filter(
                sqid__in=membership_ids,
                cohort=cohort,
            ).select_related('plan')
        )
        found = {m.sqid for m in memberships}
        missing = [mid for mid in membership_ids if mid not in found]
        plans = [m.plan for m in memberships]
        return plans, missing

    return [], []


def _build_batch_response(details, missing):
    for mid in missing:
        details.append({'sqid': mid, 'status': 'FAILED', 'error': 'Not found in cohort'})
    succeeded = sum(1 for d in details if d['status'] == 'SUCCEEDED')
    failed = sum(1 for d in details if d['status'] == 'FAILED')
    return {'total': len(details), 'succeeded': succeeded, 'failed': failed, 'details': details}


def batch_pause_plans(cohort, plan_ids=None, membership_ids=None):
    plans, missing = _resolve_plans_and_missing(cohort, plan_ids=plan_ids, membership_ids=membership_ids)
    details = []
    for plan in plans:
        try:
            if plan.status != PayPlan.Status.ACTIVE:
                raise ValueError("Only ACTIVE plans can be paused.")
            PayPlan.objects.filter(pk=plan.pk).update(status=PayPlan.Status.PAUSED)
            CohortMembership.objects.filter(cohort=cohort, plan=plan).update(status=CohortMembership.Status.PAUSED)
            details.append({'sqid': plan.sqid, 'status': 'SUCCEEDED', 'error': None})
        except Exception as e:
            details.append({'sqid': plan.sqid, 'status': 'FAILED', 'error': str(e)})
    return _build_batch_response(details, missing)


def batch_resume_plans(cohort, plan_ids=None, membership_ids=None):
    plans, missing = _resolve_plans_and_missing(cohort, plan_ids=plan_ids, membership_ids=membership_ids)
    details = []
    for plan in plans:
        try:
            if plan.status != PayPlan.Status.PAUSED:
                raise ValueError("Only PAUSED plans can be resumed.")
            PayPlan.objects.filter(pk=plan.pk).update(status=PayPlan.Status.ACTIVE)
            CohortMembership.objects.filter(cohort=cohort, plan=plan).update(status=CohortMembership.Status.ACTIVE)
            details.append({'sqid': plan.sqid, 'status': 'SUCCEEDED', 'error': None})
        except Exception as e:
            details.append({'sqid': plan.sqid, 'status': 'FAILED', 'error': str(e)})
    return _build_batch_response(details, missing)


def batch_retry_plans(cohort, plan_ids=None, membership_ids=None):
    plans, missing = _resolve_plans_and_missing(cohort, plan_ids=plan_ids, membership_ids=membership_ids)
    details = []
    for plan in plans:
        try:
            membership = plan.cohort_membership
            if membership.status != CohortMembership.Status.FAILED:
                raise ValueError("Only FAILED memberships can be retried.")
            membership.status = CohortMembership.Status.ACTIVE
            membership.save(update_fields=['status'])
            PayPlan.objects.filter(pk=plan.pk).update(status=PayPlan.Status.ACTIVE)
            details.append({'sqid': plan.sqid, 'status': 'SUCCEEDED', 'error': None})
        except Exception as e:
            details.append({'sqid': plan.sqid, 'status': 'FAILED', 'error': str(e)})
    return _build_batch_response(details, missing)
