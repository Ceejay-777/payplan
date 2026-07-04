import factory
from .models import PayPlan
from core.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    # password = factory.PostGenerationMethodCall('set_password', 'password123')

class PayPlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PayPlan
    
    title = factory.Faker('sentence', nb_words=3)
    amount = 100.00
    frequency = PayPlan.Frequency.MONTHLY
    receiver_account_number = '1234567890'
    receiver_bank_code = '011'
    receiver_account_name = 'Test Receiver'
    payment_link_token = factory.Sequence(lambda n: f"token{n}")
    status = PayPlan.Status.DRAFT
