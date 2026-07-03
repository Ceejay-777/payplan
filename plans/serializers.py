from rest_framework import serializers
from .models import PayPlan, CancellationRequest
from payplan.mixins import StrictFieldsMixin

class ResolveBankSerializer(serializers.Serializer):
    account_number = serializers.CharField()
    bank_code = serializers.CharField()
    
    account_name = serializers.CharField(read_only=True)
    resolution_token = serializers.CharField(read_only=True)
    

class PayPlanSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)

    class Meta:
        model = PayPlan
        fields = [
            'sqid', 'title', 'description', 'amount', 'currency', 
            'frequency', 'custom_interval_days', 'plan_type', 'status',
            'receiver_name', 'creator_name', 'payment_link_token', 
            'next_billing_date', 'billing_count',
            'max_billing_cycles', 'started_at', 'ends_at', 'created_at',
            'card_last_four', 'card_type'
        ]
        read_only_fields = fields
        
class CreatePayPlanReadSerializer(serializers.Serializer):
    plan = PayPlanSerializer(read_only=True)
    checkout_link = serializers.CharField(read_only=True)

class CreateSelfFundedPayPlanSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    resolution_id = serializers.CharField(write_only=True)

    class Meta:
        model = PayPlan
        fields = [
            'title', 'description', 'amount', 'frequency', 
            'custom_interval_days', 'plan_type',
            'receiver_name', 'max_billing_cycles', 'resolution_id'
        ]

    def validate(self, attrs):
        if attrs['frequency'] == PayPlan.Frequency.CUSTOM and not attrs.get('custom_interval_days'):
            raise serializers.ValidationError("custom_interval_days is required for CUSTOM frequency.")
        
        return attrs

class PlanLinkSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name')

    class Meta:
        model = PayPlan
        fields = ['title', 'amount', 'frequency', 'creator_name']
        read_only_fields = fields

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
