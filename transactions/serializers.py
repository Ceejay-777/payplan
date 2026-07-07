from rest_framework import serializers
from .models import Transaction

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
