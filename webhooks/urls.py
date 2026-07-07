from django.urls import path
from .webhooks import EngineWebhookView

urlpatterns = [
    path('engine', EngineWebhookView.as_view(), name='engine-webhook'),
]