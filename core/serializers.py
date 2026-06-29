from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, SavedCard
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

class SavedCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedCard
        fields = [
            'sqid', 'last_four', 'card_type', 'is_default', 
            'is_active', 'created_at'
        ]
        read_only_fields = fields

class TokenizeCardSerializer(serializers.Serializer):
    # This might take some initial data for Nomba Checkout
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    # email is optional, will use auth user or guest email
    email = serializers.EmailField(required=False)
    
    def validate(self, attrs):
        user = self["context"].request.user
        email = attrs.get("email")
        
        if not user and not email:
            raise serializers.ValidationError("Email is required for guest checkout.")
        
        return attrs
