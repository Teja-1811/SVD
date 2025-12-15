from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from milk_agency.models import Item
from customer_portal.views import place_order
from milk_agency.models import Customer


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API (SECURE)
    """
    user = request.user   # ✅ authenticated user
    data = request.data
    items = data.get("items")

    if not items or not isinstance(items, list):
        return Response(
            {"status": "error", "message": "Items list is required"},
            status=400
        )

    order_items = []

    for i in items:
        item_id = i.get("item_id")
        quantity = i.get("quantity")

        if not item_id or not quantity or quantity <= 0:
            return Response(
                {"status": "error", "message": "Invalid item data"},
                status=400
            )

        try:
            item_obj = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return Response(
                {"status": "error", "message": f"Item {item_id} not found"},
                status=404
            )

        order_items.append({
            "item": item_obj,
            "quantity": quantity
        })

    customer = Customer.objects.get(user=user)
    # Call existing business logic
    order_response = place_order(customer, order_items)

    if order_response.get("status") == "success":
        return Response({
            "status": "success",
            "message": "Order placed successfully",
            "order_id": order_response.get("order_id")
        })

    return Response(
        {"status": "error", "message": "Order placement failed"},
        status=500
    )
