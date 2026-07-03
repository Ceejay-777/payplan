import json
import hashlib
import hmac

from drf_spectacular.utils import extend_schema
import sentry_sdk

from django.conf import settings
from django.http import HttpResponse

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .webhookshandlers import (
    handle_billing_success, handle_billing_failed, 
    handle_dunning_exhausted, handle_subscription_cancelled,
    handle_subscription_activated
)

sub_engine_api_key = settings.SUB_ENGINE_API_KEY

EVENT_HANDLERS = {
    "subscription.activated": handle_subscription_activated,
    "payment.succeeded": handle_billing_success,
}

@extend_schema(exclude=True)
class EngineWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get('X-PayPlan-Signature')
        
        self.verify_signature(payload, signature)
            
        try:
            event = json.loads(payload)
            event_type = event.get('event')
            data = event.get('data')
            
            handler = EVENT_HANDLERS.get(event_type)
            
            if handler is None:
                sentry_sdk.logger.warning("Unhandled Sub engine webhook event type: {event_type}", event_type=event_type)
            else:
                handler(data)
                sentry_sdk.logger.info("Sub engine webhook handled: {event_type}", event_type=event_type,)
                
            return HttpResponse(status=status.HTTP_200)
        
        except Exception as e:
            sentry_sdk.logger.error(
                "Error processing Sub engine webhook",
                exc_info=True,
                extra={"payload": payload.decode('utf-8'), "signature": signature}
            )
            return Response({"detail": "Error processing sub engine webhook"}, status=status.HTTP_500)

    def verify_signature(self, payload, signature):
        hashed = hmac.new(
            sub_engine_api_key.encode(),
            msg=payload,
            digestmod=hashlib.sha512
        ).hexdigest()
        
        if not signature or signature != hashed:
            sentry_sdk.logger.warning(
                "Sub engine webhook signature validation failed",
                attributes={"provided_signature": signature or "missing", "payload": payload.decode('utf-8')},
            )
            
            return Response({"detail": "Invalid signature"}, status=status.HTTP_403)
        
        # secret = settings.ENGINE_WEBHOOK_SECRET.encode()
        # expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        # return hmac.compare_digest(expected, signature)
        return True
