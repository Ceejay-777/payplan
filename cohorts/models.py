from django.db import models

from core.models import User
from payplan.models import BaseModel
from plans.models import PayPlan


class Cohort(BaseModel):
    class Frequency(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        ANNUAL = 'ANNUAL', 'Annual'
        CUSTOM = 'CUSTOM', 'Custom'

    class ProrationMode(models.TextChoices):
        NEXT_CYCLE = 'next_cycle', 'Next Cycle'
        PRO_RATED = 'pro-rated', 'Pro-rated'
        FULL_CYCLE = 'full_cycle', 'Full Cycle'

    class Visibility(models.TextChoices):
        CLOSED = 'closed', 'Closed'
        OPEN = 'open', 'Open'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cohorts')
    frequency = models.CharField(choices=Frequency.choices, max_length=10)
    interval_count = models.PositiveIntegerField(default=1)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    proration_mode = models.CharField(choices=ProrationMode.choices, max_length=20, default=ProrationMode.PRO_RATED)
    visibility = models.CharField(choices=Visibility.choices, max_length=10, default=Visibility.CLOSED)
    receiver_account_name = models.CharField(max_length=255)
    receiver_account_number = models.CharField(max_length=20)
    receiver_bank_code = models.CharField(max_length=10)
    saved_bank_account = models.ForeignKey(
        'SavedBankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='cohorts'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (by {self.organizer.email})"


class CohortMembership(BaseModel):
    class Status(models.TextChoices):
        INVITED = 'invited', 'Invited'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='memberships')
    plan = models.OneToOneField(PayPlan, on_delete=models.CASCADE, related_name='cohort_membership')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(choices=Status.choices, max_length=20, default=Status.INVITED)
    metadata = models.JSONField(default=dict, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cohort", "plan"],
                name="unique_cohort_membership",
            )
        ]

    def __str__(self):
        return f"Membership of {self.plan.title} in {self.cohort.name}"


class SavedBankAccount(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_bank_accounts')
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20)
    bank_code = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=100, blank=True)
    status = models.CharField(choices=Status.choices, max_length=10, default=Status.ACTIVE)
    is_default = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account_number", "bank_code"],
                name="unique_saved_bank_account",
            )
        ]

    def __str__(self):
        return f"{self.account_name} ({self.account_number}, {self.bank_code})"
