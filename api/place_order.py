from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from milk_agency.models import Item
from customer_portal.models import CustomerOrder, CustomerOrderItem

@api_view(["POST"])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API
    """
    try:
        customer = request.user
        data = request.data
        items = data.get("items", [])

        if not items:
            return Response({
                "success": False,
                "message": "No items selected"
            }, status=400)

        order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        order = CustomerOrder.objects.create(
            order_number=order_number,
            customer=customer,
            created_by=customer
        )

        total_amount = 0

        for i in items:
            product = Item.objects.get(id=i["product_id"])
            qty = int(i["qty"])
            price = float(i["price"])

            if qty <= 0:
                continue

            line_total = qty * price

            CustomerOrderItem.objects.create(
                order=order,
                item=product,
                requested_quantity=qty,
                requested_price=price,
                requested_total=line_total
            )

            # reduce stock
            product.stock_quantity -= qty
            product.save()

            total_amount += line_total

        order.total_amount = total_amount
        order.approved_total_amount = total_amount
        order.save()

        return Response({
            "success": True,
            "message": "Order placed successfully",
            "order_number": order.order_number,
            "order_id": order.id
        })

    except Exception as e:
        return Response({
            "success": False,
            "message": str(e)
        }, status=500)
