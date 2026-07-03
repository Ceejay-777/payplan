from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import User, OTP
from payplan.utils.email_service import send_html_email

@transaction.atomic
def create_user(validated_data):
    email = validated_data.get("email")
    exisiting_inactive_user = User.objects.filter(email=email, is_active=False).first()
    
    if exisiting_inactive_user:
        return exisiting_inactive_user.delete()
    
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
