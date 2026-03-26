from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import SubscriptionPause

from .user_api_helpers import get_customer_or_response, get_latest_subscription


@api_view(["POST"])
def subscription_pause_resume_api(request):
    user_id = request.data.get("user_id")
    action = (request.data.get("action") or "").strip().lower()

    if action not in {"pause", "resume"}:
        return Response(
            {"error": "action must be 'pause' or 'resume'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    customer, error = get_customer_or_response(user_id, allow_frozen=False)
    if error:
        return error

    if action == "pause":
        active_subscription = get_latest_subscription(customer, active_only=True)
        if not active_subscription:
            return Response({"error": "No active subscription found"}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.localdate()
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response(
                {"error": "reason is required for pause"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_pause = SubscriptionPause.objects.filter(
            subscription=active_subscription,
            pause_date=today,
            is_resumed=False,
        ).first()
        if existing_pause:
            return Response(
                {
                    "status": "already_paused",
                    "subscription_id": active_subscription.id,
                    "pause_date": existing_pause.pause_date,
                    "reason": existing_pause.reason,
                },
                status=200,
            )

        pause = SubscriptionPause.objects.create(
            subscription=active_subscription,
            pause_date=today,
            reason=reason,
            is_resumed=False,
        )
        active_subscription.is_active = False
        active_subscription.save(update_fields=["is_active"])

        return Response(
            {
                "status": "paused",
                "subscription_id": active_subscription.id,
                "pause_date": pause.pause_date,
                "reason": pause.reason,
            },
            status=200,
        )

    active_subscription = get_latest_subscription(customer, active_only=False)
    if not active_subscription:
        return Response({"error": "No subscription found to resume"}, status=status.HTTP_404_NOT_FOUND)

    pause = (
        SubscriptionPause.objects.filter(subscription=active_subscription, is_resumed=False)
        .order_by("-pause_date", "-id")
        .first()
    )
    if not pause:
        return Response({"error": "No active pause to resume"}, status=status.HTTP_400_BAD_REQUEST)

    pause.resume()

    return Response(
        {
            "status": "resumed",
            "subscription_id": active_subscription.id,
            "pause_date": pause.pause_date,
            "resume_date": pause.resume_date,
        },
        status=200,
    )
