from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.utils import timezone
from payplan.models import BaseModel
from payplan.utils.generate import generate_otp as utils_generate_otp

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', User.Role.REGISTERED)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    class Role(models.TextChoices):
        REGISTERED = 'REGISTERED', 'Registered'
        GUEST      = 'GUEST',      'Guest'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.REGISTERED
    )
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    sub_engine_customer_id = models.CharField(max_length=255, null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return f"{self.email} ({self.role})"

def default_expiry():
    return timezone.now() + timedelta(minutes=10)


class OTP(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="otp")
    otp = models.CharField(max_length=6)  
    expiry = models.DateTimeField(default=default_expiry)
    verified = models.BooleanField(default=False)
    
    @classmethod
    def generate_otp(cls, user, expiry_minutes=10) -> str:
        otp_code = utils_generate_otp()
        expiry_time = timezone.now() + timedelta(minutes=expiry_minutes)
        created_at = timezone.now()

        otp_instance, _ = cls.objects.update_or_create(
            user=user,
            defaults={
                "otp": otp_code,
                "expiry": expiry_time,
                "verified": False,
                "created_at": created_at
            }
        )
        return otp_instance.otp

    def is_expired(self):
        return timezone.now() > self.expiry

    def verify(self, otp): 
        if self.verified:
            return False, "OTP already used"

        if self.is_expired():
            return False, "This OTP has expired"

        if self.otp != otp:
            return False, "Invalid OTP"

        self.verified = True
        self.save(update_fields=["verified"])
        return True, "OTP verified successfully"

