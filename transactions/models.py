from django.db import models
from payplan.models import BaseModel
from plans.models import PayPlan

class Transaction(BaseModel):
    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Pending'
        SUCCESS  = 'SUCCESS',  'Success'
        FAILED   = 'FAILED',   'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    plan = models.ForeignKey(PayPlan, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(choices=Status.choices, max_length=10, default=Status.PENDING)
    nomba_reference = models.CharField(max_length=255, null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    billing_cycle_number = models.IntegerField()
    charged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.sqid} for {self.plan.title} (Cycle {self.billing_cycle_number})"

class DunningAttempt(BaseModel):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        SUCCESS   = 'SUCCESS',   'Success'
        FAILED    = 'FAILED',    'Failed'

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='dunning_attempts')
    attempt_number = models.IntegerField()
    scheduled_at = models.DateTimeField()
    attempted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(choices=Status.choices, max_length=10, default=Status.SCHEDULED)
    failure_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Dunning Attempt {self.attempt_number} for Transaction {self.transaction.sqid}"
