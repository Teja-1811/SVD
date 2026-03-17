from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from milk_agency.models import CustomerSubscription, SubscriptionPause, Customer


def _get_latest_subscription(customer_id):
    return CustomerSubscription.objects.filter(customer_id=customer_id, is_active=True).order_by("-start_date").first()


@api_view(["POST"])
def subscription_pause_resume_api(request):
    """
    Pause or resume a user's latest active subscription.
    Request body:
      - user_id (required)
      - action: "pause" or "resume" (required)
      - reason: optional (only for pause)
    """
    user_id = request.data.get("user_id")
    action = (request.data.get("action") or "").lower()

    if not user_id:
        return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    if action not in ("pause", "resume"):
        return Response({"error": "action must be 'pause' or 'resume'"}, status=status.HTTP_400_BAD_REQUEST)

    customer = get_object_or_404(Customer, id=user_id, frozen=False)
    subscription = _get_latest_subscription(customer.id)
    if not subscription:
        return Response({"error": "No active subscription found"}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.localdate()

    if action == "pause":
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"error": "reason is required for pause"}, status=status.HTTP_400_BAD_REQUEST)

        existing_pause = SubscriptionPause.objects.filter(
            subscription=subscription,
            pause_date=today,
            is_resumed=False,
        ).first()
        if existing_pause:
            return Response(
                {
                    "status": "already_paused",
                    "pause_date": existing_pause.pause_date,
                    "reason": existing_pause.reason,
                },
                status=200,
            )

        pause = SubscriptionPause.objects.create(
            subscription=subscription,
            pause_date=today,
            reason=reason,
            is_resumed=False,
        )
        return Response(
            {
                "status": "paused",
                "subscription_id": subscription.id,
                "pause_date": pause.pause_date,
                "reason": pause.reason,
            },
            status=200,
        )

    # resume
    pause = (
        SubscriptionPause.objects.filter(subscription=subscription, is_resumed=False)
        .order_by("-pause_date")
        .first()
    )
    if not pause:
        return Response({"error": "No active pause to resume"}, status=status.HTTP_400_BAD_REQUEST)

    pause.resume()

    return Response(
        {
            "status": "resumed",
            "subscription_id": subscription.id,
            "pause_date": pause.pause_date,
            "resume_date": pause.resume_date,
        },
        status=200,
    )
