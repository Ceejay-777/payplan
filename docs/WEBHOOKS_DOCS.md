# Webhooks Documentation

The API uses webhooks to notify your application about events that happen in your account. When an event occurs, we send an HTTP POST request to the URLs you have registered.

## Configuring Webhooks

You can manage your webhook endpoints using the Developer API:

- **List endpoints:** `GET /api/developer/webhooks/endpoints/`
- **Register an endpoint:** `POST /api/developer/webhooks/endpoints/`
  - Payload: `{"url": "YOUR_ENDPOINT_URL", "description": "Optional description", "secret": "Optional secret"}`
- **Delete an endpoint:** `DELETE /api/developer/webhooks/endpoints/{id}/`

## Event Types and Payloads

The following events are emitted by the system:

### Customer Events
- `customer.created`:
  - Payload: `{"customer_id": "UUID"}`
- `customer.updated`:
  - Payload: `{"customer_id": "UUID", "changes": {...}}`
- `customer.deleted`:
  - Payload: `{"customer_id": "UUID"}`

### Plan Events
- `plan.created`:
  - Payload: `{"plan_id": "UUID"}`
- `plan.updated`:
  - Payload: `{"plan_id": "UUID", "changes": {...}}`
- `plan.deleted`:
  - Payload: `{"plan_id": "UUID"}`

### Subscription Events
- `subscription.created`:
  - Payload: `{"subscription_id": "UUID", "status": "string"}`
- `subscription.trialing`:
  - Payload: `{"subscription_id": "UUID"}`
- `subscription.activated`:
  - Payload: `{"subscription_id": "UUID", "invoice_id": "UUID"}`
- `subscription.canceled`:
  - Payload: `{"subscription_id": "UUID", "at_period_end": boolean}`
- `subscription.reactivated`:
  - Payload: `{"subscription_id": "UUID"}`
- `subscription.plan_changed`:
  - Payload: `{"subscription_id": "UUID", "from_plan": "UUID", "to_plan": "UUID", "proration_amount": int, "proration_mode": "string"}`
- `subscription.updated`:
  - Payload: `{"subscription_id": "UUID", "changes": {...}}`

### Invoice Events
- `invoice.created`:
  - Payload: `{"invoice_id": "UUID", "amount_due": int}`
- `invoice.paid`:
  - Payload: `{"invoice_id": "UUID", "amount_paid": int}`
- `invoice.voided`:
  - Payload: `{"invoice_id": "UUID"}`

### Payment Events
- `payment.created`:
  - Payload: `{"payment_id": "UUID", "invoice_id": "UUID"}`
- `payment.succeeded`:
  - Payload: `{"payment_id": "UUID", "nomba_reference": "string"}`
- `payment.failed`:
  - Payload: `{"payment_id": "UUID", "failure_code": "string", "failure_message": "string"}`

### Dunning Events
- `dunning.attempt_scheduled`:
  - Payload: `{"dunning_attempt_id": "UUID", "attempt_number": int}`
- `dunning.attempt_failed`:
  - Payload: `{"dunning_attempt_id": "UUID"}`
- `dunning.exhausted`:
  - Payload: `{"subscription_id": "UUID"}`

### Coupon Events
- `coupon.created`:
  - Payload: `{"coupon_id": "UUID"}`
- `coupon.updated`:
  - Payload: `{"coupon_id": "UUID", "changes": {...}}`
- `coupon.redeemed`:
  - Payload: `{"coupon_id": "UUID", "times_redeemed": int}`
- `coupon.deleted`:
  - Payload: `{"coupon_id": "UUID"}`

### Webhook Events
- `webhook.endpoint_created`:
  - Payload: `{"webhook_endpoint_id": "UUID", "url": "string"}`
- `webhook.endpoint_removed`:
  - Payload: `{"webhook_endpoint_id": "UUID"}`

## Receiving Webhooks

Your server must be able to receive HTTP POST requests. Each request will contain a JSON payload describing the event, sent to the URL you configured.

You can inspect the history of events sent to your endpoints using `GET /api/developer/webhooks/events/`. If an event fails to deliver, you can retry it using `POST /api/developer/webhooks/events/{id}/retry/`.
