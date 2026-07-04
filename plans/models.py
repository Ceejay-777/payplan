from django.db import models
from django.core.exceptions import ValidationError

from django.utils import timezone
from payplan.models import BaseModel
from core.models import User

class PayPlan(BaseModel):
    class Frequency(models.TextChoices):
        DAILY   = 'DAILY',   'Daily'
        WEEKLY  = 'WEEKLY',  'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        ANNUAL  = 'ANNUAL',  'Annual'
        CUSTOM  = 'CUSTOM',  'Custom'

    class PlanType(models.TextChoices):
        OPEN   = 'OPEN',   'Open'
        CLOSED = 'CLOSED', 'Closed'

    class Status(models.TextChoices):
        DRAFT            = 'DRAFT',            'Draft'
        AWAITING_FUNDING = 'AWAITING_FUNDING', 'Awaiting Funding'
        ACTIVE           = 'ACTIVE',           'Active'
        PAUSED           = 'PAUSED',           'Paused'
        CANCELLED        = 'CANCELLED',        'Cancelled'
        COMPLETED        = 'COMPLETED',        'Completed'
        EXPIRED          = 'EXPIRED',          'Expired'

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_plans', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    frequency = models.CharField(choices=Frequency.choices, max_length=10)
    custom_interval_days = models.IntegerField(null=True, blank=True)
    
    plan_type = models.CharField(choices=PlanType.choices, max_length=10, default=PlanType.OPEN)
    status = models.CharField(choices=Status.choices, max_length=20, default=Status.DRAFT)
    
    receiver_account_number = models.CharField(max_length=20)
    receiver_bank_code = models.CharField(max_length=10)
    receiver_account_name = models.CharField(max_length=255)
    receiver_name = models.CharField(max_length=255, null=True, blank=True) 
    
    payer_email = models.EmailField(null=True, blank=True)
    payment_link_token = models.CharField(max_length=64, unique=True)
    payment_link_expires_at = models.DateTimeField(null=True, blank=True)
    
    #TODO: Update this to payment
    card_last_four = models.CharField(max_length=4, null=True, blank=True)
    card_type = models.CharField(max_length=20, null=True, blank=True)
    
    subscription_engine_id = models.CharField(max_length=255, null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    billing_count = models.IntegerField(default=0)
    max_billing_cycles = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if (self.status != self.Status.DRAFT) and not self.creator:
            raise ValidationError(
                "PayPlan cannot leave DRAFT status without a creator assigned."
            )
        super().save(*args, **kwargs)
    
class PayPlanEvent(models.Model):
    class EventTypes(models.TextChoices):
        PLAN_CREATED = "PLAN_CREATED", "Plan Created"
        SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED", "Subscription Activated"
    
    plan = models.ForeignKey(PayPlan, on_delete=models.CASCADE, related_name='audit_logs')
    event_type = models.CharField(choices=EventTypes.choices, max_length=50)
    previous_status = models.CharField(choices=PayPlan.Status.choices, max_length=40, null=True, blank=True)
    new_status = models.CharField(choices=PayPlan.Status.choices, max_length=40)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class CancellationRequest(BaseModel):
    class InitiatedBy(models.TextChoices):
        CREATOR = 'CREATOR', 'Creator'
        PAYER   = 'PAYER',   'Payer'

    class Status(models.TextChoices):
        PENDING   = 'PENDING',   'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        EXPIRED   = 'EXPIRED',   'Expired'

    plan = models.ForeignKey(PayPlan, on_delete=models.CASCADE, related_name='cancellation_requests')
    initiated_by = models.CharField(choices=InitiatedBy.choices, max_length=10)
    creator_code = models.CharField(max_length=6)
    payer_code = models.CharField(max_length=6)
    creator_confirmed = models.BooleanField(default=False)
    payer_confirmed = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    status = models.CharField(choices=Status.choices, max_length=10, default=Status.PENDING)

    def confirm_creator(self, code):
        if self.is_expired():
            return False, "Request expired"
        
        if self.creator_code != code:
            return False, "Invalid code"
        
        self.creator_confirmed = True
        self.save(update_fields=['creator_confirmed'])
        self._check_and_cancel()
        
        return True, "Creator confirmed"

    def confirm_payer(self, code):
        if self.is_expired():
            return False, "Request expired"
        
        if self.payer_code != code:
            return False, "Invalid code"
        
        self.payer_confirmed = True
        self.save(update_fields=['payer_confirmed'])
        self._check_and_cancel()
        return True, "Payer confirmed"

    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def both_confirmed(self):
        return self.creator_confirmed and self.payer_confirmed

    def _check_and_cancel(self):
        if self.both_confirmed:
            self.status = self.Status.CONFIRMED
            self.save(update_fields=['status'])
            self.plan.cancel()

    def __str__(self):
        return f"Cancellation Request for {self.plan.title}"
