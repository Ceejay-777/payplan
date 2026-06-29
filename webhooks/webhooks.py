import json
import hashlib
import hmac
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .webhookshandlers import (
    handle_billing_success, handle_billing_failed, 
    handle_dunning_exhausted, handle_subscription_cancelled
)

from drf_spectacular.utils import extend_schema

@extend_schema(exclude=True)
class EngineWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get('X-PayPlan-Signature')
        
        # if not self.verify_signature(payload, signature):
        #     return HttpResponse("Invalid signature", status=403)
            
        try:
            event = json.loads(payload)
            event_type = event.get('event')
            data = event.get('data')
            
            if event_type == 'billing.success':
                handle_billing_success(data)
            elif event_type == 'billing.failed':
                handle_billing_failed(data)
            elif event_type == 'dunning.exhausted':
                handle_dunning_exhausted(data)
            elif event_type == 'subscription.cancelled':
                handle_subscription_cancelled(data)
                
            return HttpResponse("OK", status=200)
        except Exception as e:
            # Log error
            return HttpResponse("Error processing webhook", status=500)

    def verify_signature(self, payload, signature):
        if not signature:
            return False
        # secret = settings.ENGINE_WEBHOOK_SECRET.encode()
        # expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        # return hmac.compare_digest(expected, signature)
        return True
