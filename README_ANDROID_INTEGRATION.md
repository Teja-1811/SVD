# Android Integration Guide

This project now supports Android app communication for:

- login via token auth
- FCM push token registration
- order create/edit/delete
- Paytm payment preparation and payment status checks
- customer dashboard, bills, orders, subscriptions, and offers APIs
- admin notifications when customers or users take important actions

## 1. Login

Endpoint:

`POST /api/auth/login/`

Request body:

```json
{
  "phone": "8886307827",
  "password": "your-password"
}
```

Response includes:

- `token`
- `role`
- `user_id`
- `capabilities.push_registration`
- `capabilities.push_unregistration`
- `capabilities.prepare_payment_order`

Use the token in future requests:

`Authorization: Token <token>`

## 2. Register Android FCM Token

After login, get the device FCM token from the Android app and register it.

Endpoint:

`POST /api/mobile/push/register/`

Headers:

`Authorization: Token <token>`

Request body:

```json
{
  "token": "ANDROID_FCM_TOKEN",
  "device_type": "android",
  "device_name": "Samsung A15",
  "app_version": "1.0.0"
}
```

Unregister on logout:

`POST /api/mobile/push/unregister/`

```json
{
  "token": "ANDROID_FCM_TOKEN"
}
```

## 3. Customer and User APIs

Already available for Android use:

- `GET /api/customer-dashboard/`
- `GET /api/user/dashboard/`
- `GET /api/customer/invoices/`
- `GET /api/user/bills/`
- `GET /api/user/orders/<order_id>/`
- `GET /api/user/subscriptions/current/`
- `GET /api/user/subscriptions/history/`
- `GET /api/customer/offers/`
- `GET /api/user/offers/`

Some older endpoints use `user_id` in query/body instead of token identity. Prefer token-auth endpoints where available.

## 4. Order APIs for Android

Token-auth order APIs:

- `POST /api/user/orders/create/`
- `PUT/PATCH /api/user/orders/<order_id>/edit/`
- `DELETE /api/user/orders/<order_id>/delete/`
- `GET /api/user/orders/pending/`

Request example:

```json
{
  "items": [
    { "item_id": 1, "quantity": 2 },
    { "item_id": 7, "quantity": 1 }
  ],
  "delivery_date": "2026-04-10"
}
```

## 5. Mobile Payment Flow

Prepare a payable order:

`POST /api/mobile/payments/prepare/`

```json
{
  "items": [
    { "item_id": 1, "quantity": 2 }
  ],
  "delivery_date": "2026-04-10",
  "payment_method": "PAYTM"
}
```

Response contains:

- `order_id`
- `order_number`
- `grand_total`
- `paytm.mid`
- `paytm.order_id`
- `paytm.txn_token`
- `paytm.gateway_url`

The Android app should open Paytm using the returned payload.

To check current gateway status:

`GET /api/mobile/payments/status/<order_id>/`

## 6. Push Notification Behavior

Customer/user devices receive push notifications for:

- order confirmed
- order rejected
- order delivery status changes
- subscription delivery status changes

Admin devices receive push notifications for:

- retailer/user placed order
- retailer/user updated order
- retailer/user deleted order
- enquiry submitted
- customer payment recorded
- profile updated
- subscription paused/resumed

## 7. Android App Firebase Requirements

The Android app must add:

- `google-services.json`
- Firebase Messaging SDK
- `FirebaseMessagingService`

Required Android behavior:

1. login to get server auth token
2. fetch Android FCM token
3. call `/api/mobile/push/register/`
4. handle foreground/background notifications
5. unregister token on logout if desired

## 8. Suggested Android Notification Payload Handling

Use `data.click_action` when present.

Examples:

- `/customer/` -> customer home
- `/users/orders/123/` -> user order detail
- `/milk_agency/orders/123/` -> admin order review

Map these URLs to Android screens where appropriate.

## 9. Notes

- Web push uses VAPID keys.
- Android native FCM does not use the web VAPID key.
- Django backend now supports both web and android device tokens through `PushDevice`.
