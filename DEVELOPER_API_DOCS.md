# Developer API Documentation

All endpoints in the Developer API require `IsAPIKeyAuthenticated` permission.

## Base Path
All endpoints are prefixed with `/api/developer/` (implied by the `developer_api` namespace).

## Endpoints

| Resource | Method | Path | Description | Required Payload Fields |
| :--- | :--- | :--- | :--- | :--- |
| **Customers** | GET | `/customers/` | List customers | N/A |
| | POST | `/customers/` | Create a customer | `email`, `name`, `metadata` (optional), `external_id` (optional) |
| | GET | `/customers/{id}/` | Retrieve a customer | N/A |
| | PUT/PATCH | `/customers/{id}/` | Update a customer | `email`, `name`, `metadata` (optional), `external_id` (optional) |
| | DELETE | `/customers/{id}/` | Delete a customer | N/A |
| | GET | `/customers/{id}/payment-methods/` | List payment methods | N/A |
| | POST | `/customers/{id}/payment-methods/` | Attach payment method | `type`, `nomba_token`, `last4`, `expiry_month`, `expiry_year`, `metadata` (optional) |
| | DELETE | `/customers/{id}/payment-methods/{pm_id}/` | Detach payment method | N/A |
| | POST | `/customers/{id}/payment-methods/{pm_id}/set-default/` | Set default payment method | N/A |
| **Plans** | GET | `/plans/` | List plans | N/A |
| | POST | `/plans/` | Create a plan | `name`, `amount`, `currency`, `interval`, `interval_count`, `trial_period_days` (optional), `metadata` (optional) |
| | GET | `/plans/{id}/` | Retrieve a plan | N/A |
| | PUT/PATCH | `/plans/{id}/` | Update a plan | `name`, `amount`, `currency`, `interval`, `interval_count`, `trial_period_days`, `is_active`, `metadata` |
| | DELETE | `/plans/{id}/` | Delete a plan | N/A |
| **Subscriptions** | GET | `/subscriptions/` | List subscriptions | N/A |
| | POST | `/subscriptions/` | Create a subscription | `customer` (ID), `plan` (ID), `payment_method` (ID, optional), `metadata` (optional) |
| | GET | `/subscriptions/{id}/` | Retrieve a subscription | N/A |
| | PUT/PATCH | `/subscriptions/{id}/` | Update a subscription | `metadata` |
| | POST | `/subscriptions/{id}/cancel/` | Cancel subscription | `at_period_end` (boolean) |
| | POST | `/subscriptions/{id}/reactivate/` | Reactivate subscription | `payment_method` (ID, optional) |
| | POST | `/subscriptions/{id}/change-plan/` | Change subscription plan | `plan` (ID), `proration_mode` (str, optional), `proration_amount` (int, optional) |
| **Invoices** | GET | `/invoices/` | List invoices | N/A |
| | GET | `/invoices/{id}/` | Retrieve an invoice | N/A |
| | POST | `/invoices/{id}/void/` | Void invoice | N/A |
| | POST | `/invoices/{id}/pay/` | Pay invoice | `payment_method` (ID) |
| **Payments** | GET | `/payments/` | List payments | N/A |
| | GET | `/payments/{id}/` | Retrieve a payment | N/A |
| **Dunning Attempts**| GET | `/dunning-attempts/` | List dunning attempts | N/A |
| | GET | `/dunning-attempts/{id}/` | Retrieve dunning attempt | N/A |
| **Entitlements** | GET | `/entitlements/` | List entitlements | N/A |
| | GET | `/entitlements/{id}/` | Retrieve entitlement | N/A |
| **Webhook Endpoints**| GET | `/webhooks/endpoints/` | List webhook endpoints | N/A |
| | POST | `/webhooks/endpoints/` | Create webhook endpoint | `url`, `description`, `secret` (optional) |
| | GET | `/webhooks/endpoints/{id}/` | Retrieve webhook endpoint | N/A |
| | DELETE | `/webhooks/endpoints/{id}/` | Delete webhook endpoint | N/A |
| **Webhook Events** | GET | `/webhooks/events/` | List webhook events | N/A |
| | GET | `/webhooks/events/{id}/` | Retrieve webhook event | N/A |
| | POST | `/webhooks/events/{id}/retry/` | Retry webhook event | N/A |
| **Coupons** | GET | `/coupons/` | List coupons | N/A |
| | POST | `/coupons/` | Create a coupon | `code`, `discount_type`, `discount_value`, `max_redemptions`, `valid_until` (optional), `metadata` (optional) |
| | GET | `/coupons/{id}/` | Retrieve a coupon | N/A |
| | PUT/PATCH | `/coupons/{id}/` | Update a coupon | `code`, `discount_type`, `discount_value`, `max_redemptions`, `valid_until`, `is_active`, `metadata` |
| | DELETE | `/coupons/{id}/` | Delete a coupon | N/A |
| | POST | `/coupons/{id}/redeem/` | Redeem a coupon | N/A |
| **Audit Logs** | GET | `/audit-logs/` | List audit logs | N/A |
| | GET | `/audit-logs/{id}/` | Retrieve audit log | N/A |

---
*Note: All endpoints are protected by `IsAPIKeyAuthenticated`.*
