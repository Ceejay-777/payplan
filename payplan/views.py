from rest_framework import generics
from rest_framework.permissions import AllowAny

class PublicGenericAPIView:
    permission_classes = [AllowAny]
