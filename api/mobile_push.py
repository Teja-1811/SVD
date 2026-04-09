from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from milk_agency.models import PushDevice


VALID_DEVICE_TYPES = {"web", "android"}


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def register_mobile_push_device(request):
    token = str(request.data.get("token") or "").strip()
    if not token:
        return Response({"success": False, "message": "token is required."}, status=400)

    device_type = str(request.data.get("device_type") or "android").strip().lower()
    if device_type not in VALID_DEVICE_TYPES:
        return Response({"success": False, "message": "device_type must be web or android."}, status=400)

    device, _created = PushDevice.objects.update_or_create(
        token=token,
        defaults={
            "customer": request.user,
            "device_type": device_type,
            "device_name": str(request.data.get("device_name") or ""),
            "app_version": str(request.data.get("app_version") or ""),
            "user_agent": str(request.data.get("user_agent") or request.META.get("HTTP_USER_AGENT") or ""),
            "is_active": True,
            "last_seen_at": timezone.now(),
        },
    )
    return Response(
        {
            "success": True,
            "device_id": device.id,
            "device_type": device.device_type,
            "message": "Push device registered successfully.",
        }
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def unregister_mobile_push_device(request):
    token = str(request.data.get("token") or "").strip()
    queryset = PushDevice.objects.filter(customer=request.user, is_active=True)
    if token:
        queryset = queryset.filter(token=token)

    updated = queryset.update(is_active=False, updated_at=timezone.now())
    return Response({"success": True, "updated": updated, "message": "Push device unregistered."})
