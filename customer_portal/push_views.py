import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from milk_agency.models import PushDevice


def _parse_payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@never_cache
@csrf_exempt
@login_required
@require_POST
def register_push_device(request):
    payload = _parse_payload(request)
    if payload is None:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    token = str(payload.get("token") or "").strip()
    if not token:
        return JsonResponse({"success": False, "message": "token is required."}, status=400)

    device, _created = PushDevice.objects.update_or_create(
        token=token,
        defaults={
            "customer": request.user,
            "device_type": "web",
            "user_agent": str(payload.get("user_agent") or request.META.get("HTTP_USER_AGENT") or ""),
            "is_active": True,
            "last_seen_at": timezone.now(),
        },
    )
    return JsonResponse({"success": True, "device_id": device.id})


@never_cache
@csrf_exempt
@login_required
@require_POST
def unregister_push_device(request):
    payload = _parse_payload(request)
    if payload is None:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    token = str(payload.get("token") or "").strip()
    queryset = PushDevice.objects.filter(customer=request.user, is_active=True)
    if token:
        queryset = queryset.filter(token=token)

    updated = queryset.update(is_active=False, updated_at=timezone.now())
    return JsonResponse({"success": True, "updated": updated})
