import random
import string
from django.utils import timezone

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def generate_unique_token(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
