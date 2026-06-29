from django.utils import timezone
from .models import PayPlan

def expire_payment_links():
    """
    Scheduled task to mark expired payment links.
    """
    plans = PayPlan.objects.filter(
        status=PayPlan.Status.DRAFT,
        payment_link_expires_at__lt=timezone.now()
    )
    # Using update for efficiency
    count = plans.update(status=PayPlan.Status.EXPIRED)
    return f"Expired {count} plans"
