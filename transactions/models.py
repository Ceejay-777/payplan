from django.db import models
from payplan.models import BaseModel
from plans.models import PayPlan

class Transaction(BaseModel):
    class Status(models.TextChoices):
        CHARGE_PENDING = "CHARGE_PENDING", "Charge Pending"
        CHARGE_SUCCESS = "CHARGE_SUCCESS", "Charge Success"
        CHARGE_FAILED = "CHARGE_FAILED", "Charge Failed"
        
        PAYOUT_PENDING = "PAYOUT_PENDING", "Payout Pending" 
        PAYOUT_SUCCESS = "PAYOUT_SUCCESS", "Payout Success"
        PAYOUT_FAILED = "PAYOUT_FAILED", "Payout Failed"
        
        REFUNDED = "REFUNDED", "Refunded"

    plan = models.ForeignKey(PayPlan, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    
    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CHARGE_PENDING)
    charge_reference = models.CharField(max_length=255, null=True, blank=True)
    payout_reference = models.CharField(max_length=255, null=True, blank=True)
    
    max_payout_attempts = models.IntegerField(default=3)
    payout_failure_reason = models.TextField(null=True, blank=True)
    
    failure_reason = models.TextField(null=True, blank=True)
    billing_cycle_number = models.IntegerField()
    charged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.sqid} for {self.plan.title} (Cycle {self.billing_cycle_number})"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "billing_cycle_number", "charge_reference"],
                name="unique_transaction_per_plan_cycle",
            )
        ]
    
class TransactionEvent(models.Model):
    class EventTypes(models.TextChoices):
        TRANSACTION_CREATED = "TRANSACTION_CREATED", "Transaction Created"

        CHARGE_INITIATED = "CHARGE_INITIATED", "Charge Initiated"
        CHARGE_SUCCEEDED = "CHARGE_SUCCEEDED", "Charge Succeeded"
        CHARGE_FAILED = "CHARGE_FAILED", "Charge Failed"

        PAYOUT_INITIATED = "PAYOUT_INITIATED", "Payout Initiated"
        PAYOUT_SUCCEEDED = "PAYOUT_SUCCEEDED", "Payout Succeeded"
        PAYOUT_FAILED = "PAYOUT_FAILED", "Payout Failed"

        REFUND_INITIATED = "REFUND_INITIATED", "Refund Initiated"
        REFUND_COMPLETED = "REFUND_COMPLETED", "Refund Completed"
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='audit_logs')
    event_type = models.CharField(choices=EventTypes.choices, max_length=50)
    previous_status = models.CharField(choices=Transaction.Status.choices, max_length=40, null=True, blank=True)
    new_status = models.CharField(choices=Transaction.Status.choices, max_length=40)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class DunningAttempt(BaseModel):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        AWAITING_CONFIRMATION = 'AWAITING_CONFIRMATION', 'Awaiting Confirmation'
        SUCCESS   = 'SUCCESS',   'Success'
        FAILED    = 'FAILED',    'Failed'

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='dunning_attempts')
    attempt_number = models.IntegerField()
    scheduled_at = models.DateTimeField()
    attempted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(choices=Status.choices, max_length=10, default=Status.SCHEDULED)
    failure_reason = models.TextField(null=True, blank=True)
    payout_reference = models.CharField(max_length=255, null=True, blank=True, unique=True)

    def __str__(self):
        return f"Dunning Attempt {self.attempt_number} for Transaction {self.transaction.sqid}"
