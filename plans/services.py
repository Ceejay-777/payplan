from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from rest_framework.exceptions import ValidationError

import secrets
from datetime import timedelta
import logging

from .models import PayPlan, CancellationRequest, PayPlanEvent
from .requests import create_subscription, resolve_bank_account, create_customer, create_sub_engine_plan

from core.models import User
from payplan.utils.generate import generate_unique_token, generate_otp

logger = logging.getLogger(__name__)

BANK_RESOLUTION_TTL = 300 # 5 minutes
BASE_URL = settings.BASE_URL
PAYMENT_LINK_EXPIRY_MINUTES = settings.PAYMENT_LINK_EXPIRY_MINUTES

def _log_plan_event(plan, event_type, previous_status, new_status, metadata=None):
    event = PayPlanEvent.objects.create(
        plan=plan,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {}
    )
    
    return event

def resolve_and_cache_bank_account(resolution_data):
    """
    Resolve a bank account via Nomba, cache the result tied to this user,
    and return a one-time token the client must pass back at plan creation.
    """
    account_number = resolution_data['account_number']
    bank_code = resolution_data['bank_code']
    account_name = resolve_bank_account(account_number, bank_code)

    resolution_token = secrets.token_urlsafe(24)
    cache_key = f"bank_resolution-{resolution_token}"

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
    
def use_bank_resolution(resolution_token):
    """
    Fetch and invalidate a cached bank resolution.
    Raises ValidationError if missing, expired, or already used.
    """
    cache_key = f"bank_resolution-{resolution_token}"
    data = cache.get(cache_key)

    if not data:
        logger.warning(f"Invalid bank resolution token: {resolution_token}")
        raise ValidationError(
            "Could not resolve bank. Please try again."
        )

    cache.delete(cache_key)  
    return data

def create_self_funded_plan(creator, validated_data):
    resolution_token = validated_data.pop('resolution_token')
    receiver_bank_details = use_bank_resolution(resolution_token)
    
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
        
        plan.subscription_engine_id = sub_engine_response["id"]
        plan.order_reference = sub_engine_response.get("order_reference", "")
        
        plan.save(update_fields=['subscription_engine_id', 'order_reference', 'status'])
        
        _log_plan_event(plan=plan, event_type=PayPlanEvent.EventTypes.PLAN_CREATED, new_status=plan.status)
        
    return plan, sub_engine_response.get("checkout_link", "")

def initialize_link_funded_plan(validated_data):
    resolution_token = validated_data.pop('resolution_token')
    receiver_bank_details = use_bank_resolution(resolution_token)
    
    payment_link_token = generate_unique_token(),
    
    plan = PayPlan.objects.create(
            receiver_account_name=receiver_bank_details["account_name"],
            receiver_bank_code=receiver_bank_details["bank_code"],
            receiver_account_number=receiver_bank_details["account_number"],
            payment_link_token=payment_link_token,
            payment_link_expires_at=timezone.now() + timedelta(minutes=PAYMENT_LINK_EXPIRY_MINUTES),
            status=PayPlan.Status.DRAFT,
            **validated_data
        )
    plan.refresh_from_db()
    
    resolution_link = f"{BASE_URL}?p={plan.sqid}&plt={payment_link_token}"
    
    return plan, resolution_link

def resolve_link_funded_plan(plan, payer_email):
    guest_user = User.objects.get(email=payer_email)
    
    if not guest_user:
        # TODO: Send OTP to confirm email
        guest_user = User.objects.create(email=payer_email, role=User.Role.GUEST)
        
    if not guest_user.sub_engine_customer_id:
        customer_id = create_customer(guest_user)
        guest_user.sub_engine_customer_id = customer_id
        guest_user.save(update_fields=['sub_engine_customer_id'])
        
    
    sub_engine_plan_id = create_sub_engine_plan(plan)
    sub_engine_response = create_subscription(guest_user.sub_engine_customer_id, sub_engine_plan_id)
    
    previous_status = plan.status
    plan.creator = guest_user
    plan.subscription_engine_id = sub_engine_response["id"]
    plan.order_reference = sub_engine_response.get("order_reference", "")
    plan.status = PayPlan.Status.AWAITING_FUNDING
    
    plan.save(update_fields=['creator', 'subscription_engine_id', 'order_reference', 'status'])
    
    _log_plan_event(plan=plan, event_type=PayPlanEvent.EventTypes.PLAN_CREATED, previous_status=previous_status, new_status=plan.status)
    
    return plan, sub_engine_response.get("checkout_link", "")

def activate_plan(plan, engine_data):
    previous_status = plan.status
    
    plan.status = PayPlan.Status.ACTIVE
    plan.started_at = engine_data["started_at"]
    plan.engine_subscription_id = engine_data["subscription_id"]
    plan.next_billing_date = engine_data["next_billing_date"]
    plan.card_last_four = engine_data["card_last_four"]
    plan.card_type = engine_data["card_type"]
    
    plan.save(update_fields=['status', 'started_at', 'engine_subscription_id', 'next_billing_date', 'card_last_four', 'card_type'])
    
    _log_plan_event(plan=plan, event_type=PayPlanEvent.EventTypes.SUBSCRIPTION_ACTIVATED, previous_status=previous_status, new_status=plan.status)
    
    #TODO: Notify user
    
    return plan

def update_plan_for_charge(plan, engine_data):
    plan.billing_count += 1
    plan.next_billing_date = engine_data["next_billing_date"]
    plan.save(update_fields=['next_billing_date', 'billing_count'])
    
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
