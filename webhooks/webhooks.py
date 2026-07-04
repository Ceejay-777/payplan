import json
import hashlib
import hmac
import base64

from drf_spectacular.utils import extend_schema
import sentry_sdk

from django.conf import settings

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .webhookshandlers import (
    handle_billing_success, handle_subscription_activated
)

from .payout_handlers import handle_payout_success, handle_payout_refund

sub_engine_api_key = settings.SUB_ENGINE_API_KEY
nomba_webhook_secret = settings.NOMBA_WEBHOOK_SECRET

EVENT_HANDLERS = {
    "subscription.activated": handle_subscription_activated,
    "payment.succeeded": handle_billing_success,
}

NOMBA_EVENT_HANDLERS = {
    "payout_success": handle_payout_success,
    "payout_refund": handle_payout_refund,
}

@extend_schema(exclude=True)
class EngineWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get('X-PayPlan-Signature')
        
        verification_result = self.verify_signature(payload, signature)
        if verification_result is not True:
            return verification_result

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
                
            return Response({"detail": "Sub engine webhook processed"},status=status.HTTP_200_OK)
        
        except Exception as e:
            sentry_sdk.logger.error(
                "Error processing Sub engine webhook",
                exc_info=True,
                extra={"payload": payload.decode('utf-8'), "signature": signature}
            )
            return Response({"detail": "Error processing sub engine webhook"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            
            return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)
        
        return True
    
@extend_schema(exclude=True)
class NombaWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get('nomba-signature')
        timestamp = request.headers.get('nomba-timestamp')

        verify_result = self.verify_signature(payload, signature, timestamp)
        if verify_result is not True:
            return verify_result

        try:
            event = json.loads(payload)
            event_type = event.get('event_type')
            data = event.get('data')

            payout_reference = data.get('id')
            if payout_reference:
                sentry_sdk.set_tag("payout_reference", payout_reference)

            handler = NOMBA_EVENT_HANDLERS.get(event_type)

            if handler is None:
                sentry_sdk.logger.warning(
                    "Unhandled Nomba webhook event type: {event_type}",
                    event_type=event_type,
                )
            else:
                handler(data)
                sentry_sdk.logger.info(
                    "Nomba webhook handled: {event_type}",
                    event_type=event_type,
                )

            return Response({"detail": "Nomba webhook processed"}, status=status.HTTP_200_OK)

        except Exception:
            sentry_sdk.logger.error(
                "Error processing Nomba webhook",
                exc_info=True,
                attributes={"payload": payload.decode('utf-8'), "signature": signature},
            )
            return Response(
                {"detail": "Error processing Nomba webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def verify_signature(self, payload, signature, timestamp):
        if not signature or not timestamp:
            sentry_sdk.logger.warning(
                "Nomba webhook missing signature or timestamp",
                attributes={"signature": signature or "missing", "timestamp": timestamp or "missing"},
            )
            return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        try:
            event = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            sentry_sdk.logger.warning("Nomba webhook payload not valid JSON")
            return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        data = event.get('data', {})
        merchant = data.get('merchant', {})
        transaction = data.get('transaction', {})

        response_code = transaction.get('responseCode', '')
        if response_code == "null":
            response_code = ""

        hashing_payload = ":".join([
            event.get('event_type', ''),
            event.get('requestId', ''),
            merchant.get('userId', ''),
            merchant.get('walletId', ''),
            transaction.get('transactionId', ''),
            transaction.get('type', ''),
            transaction.get('time', ''),
            response_code,
            timestamp,
        ])

        expected = hmac.new(
            nomba_webhook_secret.encode(),
            hashing_payload.encode(),
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected).decode()

        if not hmac.compare_digest(expected_b64.lower(), signature.lower()):
            sentry_sdk.logger.warning(
                "Nomba webhook signature validation failed",
                attributes={"provided_signature": signature, "payload": payload.decode('utf-8')},
            )
            return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        return True
