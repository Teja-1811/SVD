from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from milk_agency.models import Item
from customer_portal.views import place_order

@api_view(["POST"])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API
    """
    data = request.data
    customer_id = data.get("customer_id")
    items = data.get("items")  # Expecting a list of items with 'item_id' and 'quantity'
    
    if not customer_id or not items:
        return Response({"status": "error", "message": "Customer ID and items are required."}, status=400)
    
    order_items = []
    for item in items:
        try:
            item_obj = Item.objects.get(id=item['item_id'])
            order_items.append({
                "item": item_obj,
                "quantity": item['quantity']
            })
        except Item.DoesNotExist:
            return Response({"status": "error", "message": f"Item with ID {item['item_id']} does not exist."}, status=404)
    
    order_response = place_order(customer_id, order_items)
    
    if order_response.get("status") == "success":
        return Response({"status": "success", "message": "Order placed successfully.", "order_id": order_response.get("order_id")})
    else:
        return Response({"status": "error", "message": "Failed to place order."}, status=500)