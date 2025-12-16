from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from milk_agency.models import Item, Customer
from customer_portal.views import place_order


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API (SECURE)
    """
    user = request.user
    items = request.data.get("items")

    if not isinstance(items, list) or len(items) == 0:
        return Response(
            {"status": "error", "message": "Items list is required"},
            status=400
        )

    try:
        customer = Customer.objects.get(id=user.id)
    except Customer.DoesNotExist:
        return Response(
            {"status": "error", "message": "Customer profile not found"},
            status=404
        )

    order_items = []

    try:
        with transaction.atomic():

            for i in items:
                item_id = i.get("item_id")
                quantity = i.get("quantity")

                if not isinstance(item_id, int) or not isinstance(quantity, int) or quantity <= 0:
                    return Response(
                        {"status": "error", "message": "Invalid item data"},
                        status=400
                    )

                item_obj = Item.objects.get(id=item_id)

                order_items.append({
                    "item": item_obj,
                    "quantity": quantity
                })

            order_response = place_order(customer, order_items)

            if order_response.get("status") != "success":
                raise Exception("Order failed")

            return Response({
                "status": "success",
                "message": "Order placed successfully",
                "order_id": order_response.get("order_id")
            })

    except Item.DoesNotExist:
        return Response(
            {"status": "error", "message": "One or more items not found"},
            status=404
        )

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=500
        )
