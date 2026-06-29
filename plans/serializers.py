from rest_framework import serializers
from .models import PayPlan, CancellationRequest
from core.models import SavedCard
from payplan.mixins import StrictFieldsMixin

class PayPlanSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)

    class Meta:
        model = PayPlan
        fields = [
            'sqid', 'title', 'description', 'amount', 'currency', 
            'frequency', 'custom_interval_days', 'plan_type', 'status',
            'receiver_account_number', 'receiver_bank_code', 
            'receiver_account_name', 'receiver_name', 'creator_name',
            'payment_link_token', 'next_billing_date', 'billing_count',
            'max_billing_cycles', 'started_at', 'ends_at', 'created_at'
        ]
        read_only_fields = fields

class CreatePayPlanSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    card = serializers.SlugRelatedField(
        queryset=SavedCard.objects.all(),
        slug_field='sqid',
        required=True,
        write_only=True
    )

    class Meta:
        model = PayPlan
        fields = [
            'title', 'description', 'amount', 'frequency', 
            'custom_interval_days', 'plan_type', 'receiver_account_number', 
            'receiver_bank_code', 'receiver_name', 'max_billing_cycles', 'card'
        ]

    def validate(self, attrs):
        if attrs['frequency'] == PayPlan.Frequency.CUSTOM and not attrs.get('custom_interval_days'):
            raise serializers.ValidationError("custom_interval_days is required for CUSTOM frequency.")
        
        # In actual implementation, we'd verify the card belongs to the user here
        # or handle guest card tokens.
        return attrs

class PlanLinkSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name')

    class Meta:
        model = PayPlan
        fields = ['title', 'amount', 'frequency', 'creator_name']
        read_only_fields = fields

class AuthorizePlanSerializer(serializers.Serializer):
    email = serializers.EmailField()
    card_token = serializers.CharField() # From Nomba
    last_four = serializers.CharField(max_length=4)
    card_type = serializers.CharField()

class CancellationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancellationRequest
        fields = [
            'sqid', 'initiated_by', 'creator_confirmed', 
            'payer_confirmed', 'status', 'created_at'
        ]
        read_only_fields = fields

class ConfirmCancellationSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['creator', 'payer'])
    code = serializers.CharField(max_length=6)
