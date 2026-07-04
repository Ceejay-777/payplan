from rest_framework import serializers
from .models import Transaction, DunningAttempt

class TransactionSerializer(serializers.ModelSerializer):
    plan_title = serializers.CharField(source='plan.title', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'sqid', 'plan', 'plan_title', 'amount', 'currency', 
            'status', 'charge_reference', 'failure_reason', 
            'billing_cycle_number', 'charged_at', 'created_at'
        ]
        read_only_fields = fields

class DunningAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DunningAttempt
        fields = [
            'sqid', 'transaction', 'attempt_number', 
            'scheduled_at', 'attempted_at', 'status', 
            'failure_reason', 'created_at'
        ]
        read_only_fields = fields
