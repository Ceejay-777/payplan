import uuid
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import PayPlan, CancellationRequest
from core.models import User, SavedCard
from payplan.utils.generate import generate_unique_token, generate_otp
from payplan.utils.email_service import send_email_notification
from .requests import register_with_subscription_engine, resolve_receiver_account

def create_plan(creator, validated_data):
    card = validated_data.pop('card')
    
    # Resolve account name
    receiver_account_name = resolve_receiver_account(
        validated_data['receiver_account_number'],
        validated_data['receiver_bank_code']
    )
    
    with transaction.atomic():
        plan = PayPlan.objects.create(
            creator=creator,
            receiver_account_name=receiver_account_name,
            payment_link_token=generate_unique_token(),
            **validated_data
        )
        
        # Register with engine
        engine_id = register_with_subscription_engine(plan)
        plan.engine_subscription_id = engine_id
        
        # Activate plan if it's already got a card (creator's own card maybe?)
        # But per flow, payer flow usually completes it. 
        # If creator provides card, maybe it's for them.
        plan.payer_card = card
        plan.activate()
        
        # Calculate next billing date
        plan.next_billing_date = calculate_next_billing(plan)
        plan.save(update_fields=['engine_subscription_id', 'payer_card', 'next_billing_date'])
        
        return plan

def calculate_next_billing(plan, last_date=None):
    from_date = last_date or timezone.now()
    if plan.frequency == PayPlan.Frequency.DAILY:
        return from_date + timedelta(days=1)
    elif plan.frequency == PayPlan.Frequency.WEEKLY:
        return from_date + timedelta(weeks=1)
    elif plan.frequency == PayPlan.Frequency.MONTHLY:
        # Simplistic monthly add
        return from_date + timedelta(days=30)
    elif plan.frequency == PayPlan.Frequency.ANNUAL:
        return from_date + timedelta(days=365)
    elif plan.frequency == PayPlan.Frequency.CUSTOM:
        return from_date + timedelta(days=plan.custom_interval_days)
    return from_date

def activate_plan(plan):
    plan.activate()
    plan.next_billing_date = calculate_next_billing(plan)
    plan.save(update_fields=['next_billing_date'])
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
        plan.next_billing_date = calculate_next_billing(plan)
        plan.save(update_fields=['payer_email', 'payer_card', 'next_billing_date'])
        
        # Notify payer
        send_email_notification(
            "Plan Authorized",
            f"You have authorized the plan {plan.title}.",
            [payer_email]
        )
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
        send_email_notification("Cancellation Code", f"Your code: {req.creator_code}", [plan.creator.email])
        if plan.payer_email:
            send_email_notification("Cancellation Code", f"Your code: {req.payer_code}", [plan.payer_email])
            
        return req

def confirm_cancellation(cancellation_request, role, code):
    if role == 'creator':
        return cancellation_request.confirm_creator(code)
    else:
        return cancellation_request.confirm_payer(code)

def generate_payment_link(plan):
    return f"https://payplan.app/p/{plan.payment_link_token}"
