from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from rest_framework.exceptions import ValidationError

import secrets
from datetime import timedelta
import logging

from .models import PayPlan, CancellationRequest
from .requests import create_subscription, resolve_bank_account, create_customer, create_sub_engine_plan

from core.models import User
from payplan.utils.generate import generate_unique_token, generate_otp

logger = logging.getLogger(__name__)

BANK_RESOLUTION_TTL = 300 # 5 minutes

def resolve_and_cache_bank_account(user, resolution_data):
    """
    Resolve a bank account via Nomba, cache the result tied to this user,
    and return a one-time token the client must pass back at plan creation.
    """
    account_number = resolution_data['account_number']
    bank_code = resolution_data['bank_code']
    account_name = resolve_bank_account(account_number, bank_code)

    resolution_token = secrets.token_urlsafe(24)
    cache_key = f"bank_resolution-{user.sqid}-{resolution_token}"

    cache.set(cache_key, {
        "account_number": account_number,
        "bank_code": bank_code,
        "account_name": account_name,
    }, timeout=BANK_RESOLUTION_TTL)

    return {
        "account_number": account_number,
        "bank_code": bank_code,
        "account_name": account_name,
        "resolution_token": resolution_token,
    }
    
def use_bank_resolution(user, resolution_token):
    """
    Fetch and invalidate a cached bank resolution.
    Raises ValidationError if missing, expired, or already used.
    """
    cache_key = f"bank_resolution-{user.sqid}-{resolution_token}"
    data = cache.get(cache_key)

    if not data:
        logger.warning(f"Invalid bank resolution token: {resolution_token}")
        raise ValidationError(
            "Could not resolve bank. Please try again."
        )

    cache.delete(cache_key)  
    return data

def create_self_funded_plan(creator, validated_data):
    resolution_id = validated_data.pop('resolution_id')
    receiver_bank_details = use_bank_resolution(creator, resolution_id)
    
    with transaction.atomic():
        # Check/Create sub-engine customer
        if not creator.sub_engine_customer_id:
            customer_id = create_customer(creator)
            creator.sub_engine_customer_id = customer_id
            creator.save(update_fields=['sub_engine_customer_id'])
        
        # Create plan
        plan = PayPlan.objects.create(
            creator=creator,
            receiver_account_name=receiver_bank_details["account_name"],
            receiver_bank_code=receiver_bank_details["bank_code"],
            receiver_account_number=receiver_bank_details["account_number"],
            payment_link_token=generate_unique_token(),
            status=PayPlan.Status.AWAITING_FUNDING,
            payer_email=creator.email,
            **validated_data
        )
        
        # Create sub-engine plan
        sub_engine_plan_id = create_sub_engine_plan(plan)
        
        # Create subscription
        sub_engine_response = create_subscription(creator.sub_engine_customer_id, sub_engine_plan_id)
        
        plan.engine_subscription_id = sub_engine_response["id"]
        plan.order_reference = sub_engine_response.get("order_reference", "")
        plan.status = PayPlan.Status.AWAITING_FUNDING
        plan.save(update_fields=['engine_subscription_id', 'order_reference', 'status'])
        
    return plan, sub_engine_response.get("checkout_link", "")

def activate_plan(plan, engine_data):
    """
    Called via webhook from engine.
    """
    plan.status = PayPlan.Status.ACTIVE
    plan.started_at = timezone.now()
    plan.engine_subscription_id = engine_data["subscription_id"]
    plan.next_billing_date = engine_data["next_billing_date"]
    plan.card_last_four = engine_data["card_last_four"]
    plan.card_type = engine_data["card_type"]
    plan.save()
    return plan

def cancel_plan(plan):
    plan.cancel()
    return plan

def request_cancellation(plan, initiated_by):
    with transaction.atomic():
        expires_at = timezone.now() + timedelta(hours=24)
        req = CancellationRequest.objects.create(
            plan=plan,
            initiated_by=initiated_by,
            creator_code=generate_otp(),
            payer_code=generate_otp(),
            expires_at=expires_at
        )
        return req

def confirm_cancellation(cancellation_request, role, code):
    if role == 'creator':
        return cancellation_request.confirm_creator(code)
    else:
        return cancellation_request.confirm_payer(code)

def generate_payment_link(plan):
    return f"https://payplan.app/p/{plan.payment_link_token}"
