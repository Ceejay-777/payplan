from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import User, SavedCard, OTP
from payplan.utils.email_service import send_html_email

@transaction.atomic
def create_user(validated_data):
    user = User.objects.create_user(**validated_data)
    otp  = OTP.generate_otp(user)

    send_html_email(
        subject="Verify your PayPlan email",
        template_path="emails/otp.html",
        recipient=user.email,
        context={"otp":  otp}
    )

    return user

def verify_user_email(user, otp):
    try:
        otp_obj = user.otp
    except OTP.DoesNotExist:
        raise ValidationError("No OTP record found for this user.")

    success, message = otp_obj.verify(otp)
    if not success:
        raise ValidationError(message)

    user.is_active = True
    user.save(update_fields=['is_active'])
    return user


def tokenize_card(user_or_email, amount=None):
    # Call Nomba Checkout service via requests.py
    # This is a stub for starting the checkout flow
    return "https://checkout.nomba.com/dummy-session"

def save_card(user=None, guest_email=None, card_details=None):
    # This would be called by a webhook or callback after Nomba session is complete
    with transaction.atomic():
        card = SavedCard.objects.create(
            user=user,
            guest_email=guest_email,
            nomba_token=card_details['token'],
            last_four=card_details['last_four'],
            card_type=card_details['card_type'],
        )
        return card

def set_default_card(user, card_sqid):
    with transaction.atomic():
        # Deactivate previous default
        SavedCard.objects.filter(user=user, is_default=True).update(is_default=False)
        card = SavedCard.objects.get(user=user, sqid=card_sqid)
        card.is_default = True
        card.save(update_fields=['is_default'])
        return card
