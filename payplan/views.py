from rest_framework import generics
from rest_framework.permissions import AllowAny

class PublicGenericAPIView:
    """
    Mixin for views that do not require authentication.
    """
    permission_classes = [AllowAny]
