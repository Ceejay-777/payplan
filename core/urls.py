from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from .views import (
    SignupView, LoginView, VerifyEmailView,
    RefreshTokenView, LogoutView
)

urlpatterns = [
    path('signup', SignupView.as_view(), name='signup'),
    path('login', LoginView.as_view(), name='login'),
    path('verify-email', VerifyEmailView.as_view(), name='verify-email'),
    
    path('token/refresh', RefreshTokenView.as_view(), name='token-refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
]
