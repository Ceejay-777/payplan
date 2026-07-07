from django.utils import timezone

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
    resolution_link = serializers.CharField(read_only=True)

class CreatePayPlanSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    resolution_token = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = PayPlan
        fields = [
            'title', 'description', 'amount', 'frequency', 
            'custom_interval_days', 'plan_type',
            'receiver_name', 'max_billing_cycles', 'resolution_token'
        ]

    def validate(self, attrs):
        if attrs['frequency'] == PayPlan.Frequency.CUSTOM and not attrs.get('custom_interval_days'):
            raise serializers.ValidationError("custom_interval_days is required for CUSTOM frequency.")
        
        return attrs
    
class PlanDetailSerializer(serializers.ModelSerializer):
    cohort_name = serializers.SerializerMethodField()
    cohort_description = serializers.SerializerMethodField()
    cohort_visibility = serializers.SerializerMethodField()

    class Meta:
        model = PayPlan
        fields = [
            'sqid', 'title', 'description', 'amount', 'currency',
            'frequency', 'status', 'cohort_id',
            'cohort_name', 'cohort_description', 'cohort_visibility',
        ]
        read_only_fields = fields

    def get_cohort_name(self, obj):
        if hasattr(obj, 'cohort_membership'):
            return obj.cohort_membership.cohort.name
        return None

    def get_cohort_description(self, obj):
        if hasattr(obj, 'cohort_membership'):
            return obj.cohort_membership.cohort.description
        return None

    def get_cohort_visibility(self, obj):
        if hasattr(obj, 'cohort_membership'):
            return obj.cohort_membership.cohort.visibility
        return None

class ResolveLinkFundedPayPlanSerializer(serializers.Serializer):
    payer_email = serializers.EmailField(required=True)
    plan = serializers.SlugRelatedField(queryset=PayPlan.objects.filter(status=PayPlan.Status.DRAFT), slug_field='sqid', required=True)
    payment_link_token = serializers.CharField(write_only=True)
    cohort_id = serializers.CharField(required=False, write_only=True)
    
    def validate(self, attrs):
        plan = attrs.get("plan")
        payment_link_token = attrs.get("payment_link_token")
        payment_link_expires_at = plan.payment_link_expires_at
        
        if payment_link_token != plan.payment_link_token:
            raise serializers.ValidationError(
                {"payment_link_token": "This payment link is invalid or has expired"}
            )

        if payment_link_expires_at < timezone.now():
            raise serializers.ValidationError(
                {"payment_link_token": "This payment link is invalid or has expired"}
            )
        
        return attrs

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
