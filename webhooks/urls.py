from django.urls import path
from .webhooks import EngineWebhookView, NombaWebhookView

urlpatterns = [
    path('engine', EngineWebhookView.as_view(), name='engine-webhook'),
    path('nomba', NombaWebhookView.as_view(), name='nomba-webhooks')
]
