from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from core.models import User, OTP
from core.services import create_user, verify_user_email

class OTPTestCase(TestCase):
    def setUp(self):
        self.user_data = {
            "email": "testuser@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password": "strongpassword123"
        }

    def test_create_user_generates_otp(self):
        user = create_user(self.user_data)
        self.assertIsNotNone(user)
        self.assertFalse(user.is_verified)
        
        # Verify OTP model instance exists
        otp_obj = OTP.objects.filter(user=user).first()
        self.assertIsNotNone(otp_obj)
        self.assertEqual(len(otp_obj.otp), 6)
        self.assertFalse(otp_obj.verified)
        self.assertFalse(otp_obj.is_expired())

    def test_verify_user_email_success(self):
        user = create_user(self.user_data)
        otp_obj = user.otp
        
        # Verify with correct code
        verified_user = verify_user_email(user, otp_obj.otp)
        self.assertTrue(verified_user.is_verified)
        
        # Check database states
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.verified)

    def test_verify_user_email_invalid_otp(self):
        user = create_user(self.user_data)
        
        with self.assertRaises(ValidationError) as context:
            verify_user_email(user, "000000")
            
        self.assertIn("Invalid OTP", str(context.exception))
        
        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_verify_user_email_expired_otp(self):
        user = create_user(self.user_data)
        otp_obj = user.otp
        
        # Manually expire the OTP
        otp_obj.expiry = timezone.now() - timedelta(minutes=1)
        otp_obj.save()
        
        with self.assertRaises(ValidationError) as context:
            verify_user_email(user, otp_obj.otp)
            
        self.assertIn("This OTP has expired", str(context.exception))
        
        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_verify_user_email_already_used_otp(self):
        user = create_user(self.user_data)
        otp_obj = user.otp
        
        # Verify first time
        verify_user_email(user, otp_obj.otp)
        
        # Attempt to verify second time
        with self.assertRaises(ValidationError) as context:
            verify_user_email(user, otp_obj.otp)
            
        self.assertIn("OTP already used", str(context.exception))
