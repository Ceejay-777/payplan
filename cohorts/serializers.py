from rest_framework import serializers

from payplan.mixins import StrictFieldsMixin
from .models import Cohort, CohortMembership, SavedBankAccount


class PayerDataSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    name = serializers.CharField(write_only=True, max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True)
    metadata = serializers.JSONField(default=dict, write_only=True, required=False)


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            'sqid', 'name', 'description', 'frequency', 'interval_count',
            'start_date', 'end_date', 'proration_mode', 'visibility',
            'receiver_account_name', 'receiver_account_number', 'receiver_bank_code',
            'saved_bank_account', 'created_at', 'updated_at',
        ]
        read_only_fields = ['sqid', 'created_at', 'updated_at']


class CreateCohortSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    payers = PayerDataSerializer(many=True, write_only=True, required=False)
    bank_account_id = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Cohort
        fields = [
            'name', 'description', 'frequency', 'interval_count',
            'start_date', 'end_date', 'proration_mode', 'visibility',
            'receiver_account_name', 'receiver_account_number', 'receiver_bank_code',
            'saved_bank_account', 'payers', 'bank_account_id',
        ]


class UpdateCohortSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            'name', 'description', 'frequency', 'interval_count',
            'start_date', 'end_date', 'proration_mode', 'visibility',
            'receiver_account_name', 'receiver_account_number', 'receiver_bank_code',
            'saved_bank_account',
        ]


class CohortMembershipSerializer(serializers.ModelSerializer):
    plan_sqid = serializers.CharField(source='plan.sqid', read_only=True)
    plan_title = serializers.CharField(source='plan.title', read_only=True)
    payer_email = serializers.EmailField(source='plan.payer_email', read_only=True, allow_null=True)
    resolution_link = serializers.SerializerMethodField()

    class Meta:
        model = CohortMembership
        fields = [
            'sqid', 'plan_sqid', 'plan_title', 'amount', 'status',
            'payer_email', 'resolution_link', 'joined_at', 'created_at',
        ]
        read_only_fields = fields

    def get_resolution_link(self, obj):
        plan = obj.plan
        if not plan.payment_link_token:
            return None
        from django.conf import settings
        return f"{settings.BASE_URL}?p={plan.sqid}&plt={plan.payment_link_token}&c={obj.cohort.sqid}"


class CohortDetailSerializer(CohortSerializer):
    memberships = CohortMembershipSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta(CohortSerializer.Meta):
        fields = CohortSerializer.Meta.fields + ['memberships', 'member_count']

    def get_member_count(self, obj):
        return obj.memberships.count()


class AddPayersSerializer(serializers.Serializer):
    payers = PayerDataSerializer(many=True)


class SavedBankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedBankAccount
        fields = [
            'sqid', 'account_name', 'account_number', 'bank_code',
            'bank_name', 'nickname', 'status', 'is_default',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['sqid', 'created_at', 'updated_at']


class CohortSummarySerializer(serializers.Serializer):
    total_expected = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_collected = serializers.DecimalField(max_digits=12, decimal_places=2)
    collection_percentage = serializers.FloatField()
    active_payers = serializers.IntegerField()
    total_payers = serializers.IntegerField()
    next_billing_date = serializers.DateTimeField(allow_null=True)


class BatchActionSerializer(serializers.Serializer):
    plan_ids = serializers.ListField(child=serializers.CharField(), required=False, default=None)
    membership_ids = serializers.ListField(child=serializers.CharField(), required=False, default=None)

    def validate(self, data):
        plan_ids = data.get('plan_ids')
        membership_ids = data.get('membership_ids')
        if plan_ids and membership_ids:
            raise serializers.ValidationError("Provide either plan_ids or membership_ids, not both.")
        if not plan_ids and not membership_ids:
            raise serializers.ValidationError("Provide either plan_ids or membership_ids.")
        return data


class CreateBankAccountSerializer(serializers.Serializer):
    account_number = serializers.CharField(max_length=20)
    bank_code = serializers.CharField(max_length=10)
    nickname = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_default = serializers.BooleanField(required=False, default=False)


class UpdateBankAccountSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_default = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(choices=SavedBankAccount.Status.choices, required=False)


class ResolveBankSerializer(serializers.Serializer):
    pass
