from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from milk_agency.models import Item
from customer_portal.models import CustomerOrder, CustomerOrderItem


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API
    Saves order EXACTLY like website
    """

    customer = request.user              # ✅ SAME AS WEBSITE
    items = request.data.get("items", [])

    if not isinstance(items, list) or not items:
        return Response(
            {"success": False, "message": "No items selected"},
            status=400
        )

    try:
        with transaction.atomic():

            # ✅ SAME ORDER NUMBER LOGIC
            order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

            # ✅ CREATE ORDER (IDENTICAL FIELDS)
            order = CustomerOrder.objects.create(
                order_number=order_number,
                customer=customer,
                created_by=customer,
            )

            total_amount = 0

            for i in items:
                item_id = i.get("item_id")
                qty = int(i.get("quantity", 0))
                price = float(i.get("price", 0))

                if not item_id or qty <= 0 or price <= 0:
                    return Response(
                        {"success": False, "message": "Invalid item data"},
                        status=400
                    )

                item = get_object_or_404(Item, id=item_id)

                line_total = qty * price

                # ✅ CREATE ORDER ITEM (IDENTICAL)
                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=qty,
                    requested_price=price,
                    requested_total=line_total
                )

                total_amount += line_total

            # ✅ UPDATE TOTALS (IDENTICAL)
            order.total_amount = total_amount
            order.approved_total_amount = total_amount
            order.save()

            return Response({
                "success": True,
                "order_number": order_number
            })

    except Exception as e:
        return Response(
            {"success": False, "message": str(e)},
            status=500
        )
