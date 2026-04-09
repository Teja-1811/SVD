from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .paytm_notifications import extract_paytm_params, process_paytm_notification


@csrf_exempt
@require_POST
def paytm_payment_webhook(request):
    params = extract_paytm_params(request)
    result = process_paytm_notification(params)
    order = result.get("order")

    return JsonResponse(
        {
            "success": result["success"],
            "message": result["message"],
            "order_id": getattr(order, "id", None),
            "order_number": getattr(order, "order_number", ""),
        },
        status=result["code"],
    )
