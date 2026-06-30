from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from rest_framework.exceptions import ValidationError

import secrets
from datetime import timedelta
import logging

from .models import PayPlan, CancellationRequest
from .requests import create_subscription, resolve_bank_account

from core.models import User, SavedCard
from payplan.utils.generate import generate_unique_token, generate_otp

logger = logging.getLogger(__name__)

BANK_RESOLUTION_TTL = 300 # 5 minutes

def resolve_and_cache_bank_account(user, account_number, bank_code):
    """
    Resolve a bank account via Nomba, cache the result tied to this user,
    and return a one-time token the client must pass back at plan creation.
    """
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
    card = validated_data.pop('card')
    resolution_id = validated_data.pop('resolution_id')
    
    receiver_bank_details = use_bank_resolution(creator, resolution_id)
    
    with transaction.atomic():
        plan = PayPlan.objects.create(
            creator=creator,
            
            receiver_account_name=receiver_bank_details["account_name"],
            receiver_bank_code=receiver_bank_details["bank_code"],
            receiver_account_number=receiver_bank_details["account_number"],
            
            payment_link_token=generate_unique_token(),
            payer_card = card,
            payer_email = creator.email,
            
            **validated_data
        )
        
        sub_engine_response = create_subscription(plan)
        plan.subscription_id = sub_engine_response["subscription_id"]
        plan.next_billing_date = sub_engine_response["next_billing_date"]
        
        plan.activate()
        plan.save(update_fields=['engine_subscription_id', 'payer_card', 'next_billing_date'])
        
    return plan

# def create_payment_request_plan(creator, validated_data):
#     """Creator is the receiver — plan stays DRAFT until payer authorizes via link."""
#     resolution_id = validated_data.pop('resolution_id')
#     receiver_bank_details = use_bank_resolution(creator, resolution_id)

#     plan = PayPlan.objects.create(
#         creator=creator,
#         receiver_account_name=receiver_bank_details["account_name"],
#         receiver_bank_code=receiver_bank_details["bank_code"],
#         receiver_account_number=receiver_bank_details["account_number"],
#         payment_link_token=generate_unique_token(),
#         status=PayPlan.Status.DRAFT,
#         **validated_data
#     )
#     # No card, no engine registration, no activation —
#     # all of that happens in authorize_plan() when the payer completes the link flow.
#     return plan

def activate_plan(plan):
    plan.activate()
    # plan.next_billing_date = calculate_next_billing(plan)
    # plan.save(update_fields=['next_billing_date'])
    return plan

def authorize_plan(plan, payer_email, card_details):
    with transaction.atomic():
        # Find or create SavedCard for payer
        user = User.objects.filter(email=payer_email).first()
        card = SavedCard.objects.create(
            user=user,
            guest_email=payer_email if not user else None,
            nomba_token=card_details['token'],
            last_four=card_details['last_four'],
            card_type=card_details['card_type']
        )
        
        plan.payer_email = payer_email
        plan.payer_card = card
        plan.activate()
        # plan.next_billing_date = calculate_next_billing(plan)
        plan.save(update_fields=['payer_email', 'payer_card'])
        
        # Notify payer
        # send_email_notification(
        #     "Plan Authorized",
        #     f"You have authorized the plan {plan.title}.",
        #     [payer_email]
        # )
        return plan

def cancel_plan(plan):
    plan.cancel()
    # Notify engine if needed
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
        
        # Email codes
        # send_email_notification("Cancellation Code", f"Your code: {req.creator_code}", [plan.creator.email])
        # if plan.payer_email:
        #     send_email_notification("Cancellation Code", f"Your code: {req.payer_code}", [plan.payer_email])
            
        return req

def confirm_cancellation(cancellation_request, role, code):
    if role == 'creator':
        return cancellation_request.confirm_creator(code)
    else:
        return cancellation_request.confirm_payer(code)

def generate_payment_link(plan):
    return f"https://payplan.app/p/{plan.payment_link_token}"
