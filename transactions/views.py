from rest_framework import generics, permissions
from .models import Transaction, DunningAttempt
from .serializers import TransactionSerializer
from plans.models import PayPlan
from drf_spectacular.utils import extend_schema

@extend_schema(tags=["Transactions"])
class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Authenticated user can see transactions for plans they created
        return Transaction.objects.filter(plan__creator=self.request.user)

@extend_schema(tags=["Transactions"])
class TransactionDetailView(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'sqid'

    def get_queryset(self):
        return Transaction.objects.filter(plan__creator=self.request.user)
