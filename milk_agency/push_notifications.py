import logging
from typing import Iterable

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Customer, PushDevice

logger = logging.getLogger(__name__)


def _firebase_components():
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        logger.warning("firebase-admin is not installed; push notifications are disabled.")
        return None, None, None

    try:
        app = firebase_admin.get_app("svd-push")
    except ValueError:
        credential = None
        if getattr(settings, "FIREBASE_SERVICE_ACCOUNT_INFO", None):
            credential = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_INFO)
        elif getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", ""):
            credential = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)

        if credential is None:
            logger.warning("Firebase service account credentials are missing; push notifications are disabled.")
            return None, None, None

        app = firebase_admin.initialize_app(credential, name="svd-push")

    return app, messaging, firebase_admin


def _normalize_payload(data):
    normalized = {}
    for key, value in (data or {}).items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _should_disable_token(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        fragment in message
        for fragment in [
            "registration token is not a valid fcm registration token",
            "requested entity was not found",
            "not registered",
            "unregistered",
        ]
    )


def send_push_to_devices(
    devices: Iterable[PushDevice],
    *,
    title: str,
    body: str,
    data=None,
    tag: str = "svd-update",
):
    app, messaging, _firebase_admin = _firebase_components()
    if not app or not messaging:
        return {"sent": 0, "failed": 0}

    payload = _normalize_payload(data)
    sent = 0
    failed = 0

    for device in devices:
        try:
            message_kwargs = {
                "token": device.token,
                "notification": messaging.Notification(title=title, body=body),
                "data": payload,
            }

            if device.device_type == "android":
                message_kwargs["android"] = messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        title=title,
                        body=body,
                        channel_id="default",
                    ),
                )
            else:
                message_kwargs["webpush"] = messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                        icon="/static/android-chrome-192x192.png",
                        badge="/static/favicon-32x32.png",
                        tag=tag,
                    ),
                )

            message = messaging.Message(
                **message_kwargs,
            )
            messaging.send(message, app=app)
            sent += 1
            device.last_seen_at = timezone.now()
            device.save(update_fields=["last_seen_at", "updated_at"])
        except Exception as exc:
            failed += 1
            logger.warning("Failed to send push notification to device %s: %s", device.id, exc)
            if _should_disable_token(exc):
                device.is_active = False
                device.save(update_fields=["is_active", "updated_at"])

    return {"sent": sent, "failed": failed}


def send_customer_push(customer, *, title: str, body: str, data=None, tag: str = "svd-update"):
    devices = list(
        PushDevice.objects.filter(
            customer=customer,
            is_active=True,
        )
    )
    if not devices:
        return {"sent": 0, "failed": 0}
    return send_push_to_devices(devices, title=title, body=body, data=data, tag=tag)


def _admin_queryset():
    return Customer.objects.filter(is_active=True).filter(is_staff=True) | Customer.objects.filter(is_active=True, is_superuser=True)


def send_admin_push(*, title: str, body: str, data=None, tag: str = "admin-update"):
    admin_ids = list(_admin_queryset().values_list("id", flat=True).distinct())
    devices = list(PushDevice.objects.filter(customer_id__in=admin_ids, is_active=True))
    if not devices:
        return {"sent": 0, "failed": 0}
    return send_push_to_devices(devices, title=title, body=body, data=data, tag=tag)


def _order_detail_url(order):
    if getattr(order.customer, "user_type", "").lower() == "user":
        return reverse("users:order_detail", args=[order.id])
    return reverse("customer_portal:order_detail", args=[order.id])


def _subscription_url(subscription_order):
    if getattr(subscription_order.customer, "user_type", "").lower() == "user":
        return reverse("users:subscriptions")
    return reverse("customer_portal:home")


def notify_order_confirmed(order):
    return send_customer_push(
        order.customer,
        title="Order Confirmed",
        body=f"Your order {order.order_number} has been confirmed.",
        data={
            "click_action": _order_detail_url(order),
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "tag": f"order-{order.id}",
        },
        tag=f"order-{order.id}",
    )


def notify_order_rejected(order):
    return send_customer_push(
        order.customer,
        title="Order Update",
        body=f"Your order {order.order_number} was rejected. Please contact support if needed.",
        data={
            "click_action": _order_detail_url(order),
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "tag": f"order-{order.id}",
        },
        tag=f"order-{order.id}",
    )


def notify_order_delivery_status(order, status):
    readable_status = str(status or "pending").replace("_", " ").title()
    return send_customer_push(
        order.customer,
        title="Delivery Update",
        body=f"Order {order.order_number} is now {readable_status}.",
        data={
            "click_action": _order_detail_url(order),
            "order_id": order.id,
            "order_number": order.order_number,
            "status": status or "",
            "tag": f"delivery-{order.id}",
        },
        tag=f"delivery-{order.id}",
    )


def notify_subscription_delivery_status(subscription_delivery, status):
    subscription_order = subscription_delivery.subscription_order
    item_name = getattr(getattr(subscription_order, "item", None), "name", "subscription item")
    readable_status = str(status or "pending").replace("_", " ").title()
    return send_customer_push(
        subscription_order.customer,
        title="Subscription Delivery Update",
        body=f"{item_name} is now {readable_status}.",
        data={
            "click_action": _subscription_url(subscription_order),
            "subscription_order_id": subscription_order.id,
            "status": status or "",
            "tag": f"subscription-{subscription_order.id}",
        },
        tag=f"subscription-{subscription_order.id}",
    )


def notify_admin_order_placed(order):
    actor_type = "User" if getattr(order.customer, "user_type", "").lower() == "user" else "Retailer"
    return send_admin_push(
        title="New Order Placed",
        body=f"{actor_type} {order.customer.name} placed order {order.order_number}.",
        data={
            "click_action": reverse("milk_agency:admin_order_detail", args=[order.id]),
            "order_id": order.id,
            "order_number": order.order_number,
            "customer_id": order.customer_id,
            "customer_name": order.customer.name,
            "tag": f"admin-order-{order.id}",
        },
        tag=f"admin-order-{order.id}",
    )


def notify_admin_enquiry_created(contact):
    return send_admin_push(
        title="New Enquiry",
        body=f"{contact.name} submitted an enquiry: {contact.subject}.",
        data={
            "click_action": reverse("milk_agency:admin_enquiries"),
            "contact_id": contact.id,
            "customer_id": contact.customer_id or "",
            "subject": contact.subject,
            "tag": f"admin-enquiry-{contact.id}",
        },
        tag=f"admin-enquiry-{contact.id}",
    )


def notify_admin_payment_recorded(payment):
    return send_admin_push(
        title="Customer Payment Recorded",
        body=f"{payment.customer.name} recorded a payment of Rs. {payment.amount}.",
        data={
            "click_action": reverse("milk_agency:customer_payments"),
            "payment_id": payment.id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "tag": f"admin-payment-{payment.id}",
        },
        tag=f"admin-payment-{payment.id}",
    )


def notify_admin_profile_updated(customer):
    portal_url = reverse("customer_portal:update_profile") if getattr(customer, "user_type", "").lower() != "user" else reverse("users:dashboard")
    return send_admin_push(
        title="Profile Updated",
        body=f"{customer.name} updated profile details.",
        data={
            "click_action": portal_url,
            "customer_id": customer.id,
            "customer_name": customer.name,
            "tag": f"admin-profile-{customer.id}",
        },
        tag=f"admin-profile-{customer.id}",
    )


def notify_admin_subscription_action(customer, action, reason=""):
    readable = str(action or "updated").replace("_", " ").title()
    body = f"{customer.name} {readable.lower()} their subscription."
    if reason:
        body = f"{body} Reason: {reason}"
    return send_admin_push(
        title=f"Subscription {readable}",
        body=body,
        data={
            "click_action": reverse("milk_agency:subscription_dashboard"),
            "customer_id": customer.id,
            "customer_name": customer.name,
            "action": action,
            "tag": f"admin-subscription-{customer.id}",
        },
        tag=f"admin-subscription-{customer.id}",
    )
