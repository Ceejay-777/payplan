from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import generics, status, permissions
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema
import os
import secrets

from payplan.views import PublicGenericAPIView

from .models import PayPlan, CancellationRequest
from .serializers import (
    PayPlanSerializer, CreatePayPlanSerializer, ConfirmCancellationSerializer,
    ResolveBankSerializer, CreatePayPlanReadSerializer, ResolveLinkFundedPayPlanSerializer
)
from .services import (
    create_self_funded_plan, initialize_link_funded_plan,
    request_cancellation, confirm_cancellation, resolve_link_funded_plan,
    resolve_and_cache_bank_account
)

PAYMENT_LINK_EXPIRY_MINUTES = settings.PAYMENT_LINK_EXPIRY_MINUTES

@extend_schema(tags=["Plans"])
class ResolveBankView(generics.GenericAPIView):
    serializer_class = ResolveBankSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        resolution_data = resolve_and_cache_bank_account(request.user, serializer.validated_data)
        
        return Response({"data": serializer(resolution_data).data, "detail": "Bank account resolved successfully", "status": "success"}, status=status.HTTP_200_OK)
    

@extend_schema(tags=["Plans"], summary="Create a new pay plan", responses={201: CreatePayPlanReadSerializer})
class CreateSelfFundedPlanView(generics.CreateAPIView):
    serializer_class = CreatePayPlanSerializer
    permission_classes = [permissions.IsAuthenticated] 

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan, resolution_link = create_self_funded_plan(request.user, serializer.validated_data)
        
        return Response(
            {
                "data": {"plan": PayPlanSerializer(plan).data, "resolution_link": resolution_link},
                "status": "success",
                "detail": "Plan created successfully"
            },
            status=status.HTTP_201_CREATED
        )
        
@extend_schema(tags=["Plans"], summary="Create a new link-funded pay plan", responses={201: CreatePayPlanReadSerializer})
class CreateLinkFundedPayPlan(generics.CreateAPIView):
    serializer_class = CreatePayPlanSerializer
    permission_classes = [permissions.IsAuthenticated] 

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        plan, resolution_link = initialize_link_funded_plan(validated_data)
        
        return Response(
            {
                "data": {"plan": serializer(plan).data, "resolution_link": resolution_link},
                "status": "success",
                "detail": f"This link will expire in {PAYMENT_LINK_EXPIRY_MINUTES} mins"
            },
            status=status.HTTP_201_CREATED
        )
@extend_schema(tags=["Payer Flow"])
class ResolveLinkFundedPayPlanView(PublicGenericAPIView, generics.GenericAPIView):
    serializer_class = ResolveLinkFundedPayPlanSerializer

    def post(self, request, token, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        plan, resolution_link = resolve_link_funded_plan(**validated_data)
        return Response(
            {
                "data": {"plan": PayPlanSerializer(plan).data, "resolution_link": resolution_link},
                "status": "success",
                "detail": "Plan resolved successfully"
            },
            status=status.HTTP_201_CREATED
        )
        
@extend_schema(tags=["Plans"])
class ListUserPlansView(generics.ListAPIView):
    serializer_class = PayPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PayPlan.objects.filter(creator=self.request.user)

@extend_schema(tags=["Plans"])
class RetrieveUserPlanView(generics.RetrieveAPIView):
    serializer_class = PayPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'sqid'

    def get_queryset(self):
        return PayPlan.objects.filter(creator=self.request.user)

@extend_schema(tags=["Plans"])
class PausePlanView(generics.UpdateAPIView):
    serializer_class = PayPlanSerializer
    lookup_field = 'sqid'
    http_method_names = ["patch"]

    def get_queryset(self):
        return PayPlan.objects.filter(creator=self.request.user)

    def patch(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan.status != PayPlan.Status.ACTIVE:
            return Response({"detail": "Only active plans can be paused", "status": "error"}, status=400)
        plan.pause()
        return Response({"detail": "Plan paused", "status": "success"})

@extend_schema(tags=["Plans"])
class ResumePlanView(generics.UpdateAPIView):
    serializer_class = PayPlanSerializer
    lookup_field = 'sqid'

    def get_queryset(self):
        return PayPlan.objects.filter(creator=self.request.user)

    def patch(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan.status != PayPlan.Status.PAUSED:
            return Response({"detail": "Only paused plans can be resumed", "status": "error"}, status=400)
        plan.resume()
        return Response({"detail": "Plan resumed", "status": "success"})

# Cancellation Flow
@extend_schema(tags=["Cancellation"], exclude=True)
class RequestCancellationView(generics.GenericAPIView):
    # This can be creator (auth) or payer (via token link - simplified for now)
    permission_classes = [permissions.AllowAny]

    def post(self, request, sqid, *args, **kwargs):
        plan = get_object_or_404(PayPlan, sqid=sqid)
        # Check if user is creator or payer_email matches
        # For simplicity, we'll allow initiating if details are known
        # In prod, use signed tokens or auth.
        req = request_cancellation(plan, initiated_by='CREATOR' if request.user.is_authenticated else 'PAYER')
        return Response({"detail": "Cancellation codes sent to both parties", "status": "success"})

@extend_schema(tags=["Cancellation"])
class ConfirmCancellationView(generics.GenericAPIView):
    serializer_class = ConfirmCancellationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, sqid, *args, **kwargs):
        plan = get_object_or_404(PayPlan, sqid=sqid)
        req = plan.cancellation_requests.filter(status=CancellationRequest.Status.PENDING).last()
        if not req:
            return Response({"detail": "No pending cancellation request", "status": "error"}, status=404)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        success, message = confirm_cancellation(req, serializer.validated_data['role'], serializer.validated_data['code'])
        if success:
            return Response({"detail": message, "status": "success"})
        return Response({"detail": message, "status": "error"}, status=400)
