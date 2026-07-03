from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
from payplan.mixins import StrictFieldsMixin

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['sqid', 'email', 'first_name', 'last_name', 'role', 'created_at']
        read_only_fields = fields

class SignupSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class LoginSerializer(StrictFieldsMixin, serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs['email'], password=attrs['password'])
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled")
        
        self.user = user
        return attrs

class VerifyEmailSerializer(StrictFieldsMixin, serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
