from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from .views import (
    SignupView, LoginView, VerifyEmailView, TokenizeCardView,
    SavedCardListView, SavedCardDetailView, SetDefaultCardView,
    RefreshTokenView, LogoutView
)

urlpatterns = [
    path('signup', SignupView.as_view(), name='signup'),
    path('login', LoginView.as_view(), name='login'),
    path('verify-email', VerifyEmailView.as_view(), name='verify-email'),
    
    path('token/refresh', RefreshTokenView.as_view(), name='token-refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
    
    path('cards/tokenize', TokenizeCardView.as_view(), name='tokenize-card'),
    path('cards', SavedCardListView.as_view(), name='list-cards'),
    path('cards/<slug:sqid>', SavedCardDetailView.as_view(), name='retrieve-card'),
    path('cards/<slug:sqid>/set-default', SetDefaultCardView.as_view(), name='set-default-card'),
]
