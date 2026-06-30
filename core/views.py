from django.conf import settings
from django.db import transaction

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenBlacklistView
)
from drf_spectacular.utils import extend_schema

from payplan.views import PublicGenericAPIView
from .models import User, SavedCard
from .serializers import (
    SignupSerializer, UserSerializer, LoginSerializer, 
    VerifyEmailSerializer, SavedCardSerializer, TokenizeCardSerializer
)
from .services import create_user, verify_user_email, tokenize_card, set_default_card

@extend_schema(tags=["Auth"])
class SignupView(PublicGenericAPIView, generics.CreateAPIView):
    serializer_class = SignupSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = create_user(serializer.validated_data)
        
        return Response(
            {
                "data": UserSerializer(user).data,
                "detail": "User created successfully. Please verify your email.",
                "status": "success"
            },
            status=status.HTTP_201_CREATED
        )

@extend_schema(tags=["Auth"])
class LoginView(PublicGenericAPIView, TokenObtainPairView):
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            access  = response.data.pop("access")
            refresh = response.data.pop("refresh")
            
            response.data["status"] = "success"
            response.data["detail"] = "Login successful"
            
            response.set_cookie(
                'access', access,
                httponly=True, secure=not settings.DEBUG, samesite='Lax'
            )
            response.set_cookie(
                'refresh', refresh,
                httponly=True, secure=not settings.DEBUG, samesite='Lax'
            )
        
        return response

@extend_schema(tags=["Auth"])
class RefreshTokenView(PublicGenericAPIView, TokenRefreshView):

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            return Response(
                {"detail": "Session expired, please login again."},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        request._full_data = {"refresh": refresh_token}

        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            access = response.data.get("access")

            response.set_cookie(
                'access', access,
                httponly=True, secure=not settings.DEBUG, samesite='Lax'
            )
            response.data = {"status": "success", "detail": "Token refreshed"}

        return response
        

@extend_schema(tags=["Auth"])
class LogoutView(PublicGenericAPIView, TokenBlacklistView):

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            return Response(
                {"detail": "No active session found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        request._full_data = {"refresh": refresh_token}

        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            response.delete_cookie('access')
            response.delete_cookie('refresh')
            response.data = {"status": "success", "detail": "Logged out successfully"}

        return response

@extend_schema(tags=["Auth"])
class VerifyEmailView(PublicGenericAPIView, generics.GenericAPIView):
    serializer_class = VerifyEmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = User.objects.get(email=serializer.validated_data['email'])
            verify_user_email(user, serializer.validated_data['otp'])
            
            return Response({"detail": "Email verified successfully.", "status": "success"})
        
        except User.DoesNotExist:
            return Response({"detail": "User not found", "status": "error"}, status=status.HTTP_404_NOT_FOUND)
        
        


@extend_schema(tags=["Cards"])
class TokenizeCardView(generics.GenericAPIView):
    serializer_class = TokenizeCardSerializer
    # Payer might be guest or authenticated
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_or_email = request.user if request.user.is_authenticated else serializer.validated_data.get('email')
        
        checkout_url = tokenize_card(user_or_email, serializer.validated_data.get('amount'))
        return Response({
            "data": {"checkout_url": checkout_url},
            "status": "success"
        })

@extend_schema(tags=["Cards"])
class SavedCardListView(generics.ListAPIView):
    serializer_class = SavedCardSerializer
    
    def get_queryset(self):
        return SavedCard.objects.filter(user=self.request.user, is_active=True)

@extend_schema(tags=["Cards"])
class SavedCardDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = SavedCardSerializer
    lookup_field = 'sqid'
    
    def get_queryset(self):
        return SavedCard.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

@extend_schema(tags=["Cards"])
class SetDefaultCardView(generics.UpdateAPIView):
    serializer_class = SavedCardSerializer
    lookup_field = 'sqid'
    http_method_names = ["patch"]
    
    def get_queryset(self):
        return SavedCard.objects.filter(user=self.request.user)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        card = set_default_card(request.user, instance.sqid)
        return Response({
            "data": SavedCardSerializer(card).data,
            "status": "success",
            "detail": "Default card updated"
        })
