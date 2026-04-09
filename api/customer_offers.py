from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import OfferItems, Offers


@api_view(["GET"])
def customer_offers(request):
    today = timezone.localdate()
    offers = Offers.objects.filter(
        offer_for="retailer",
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    ).order_by("end_date", "name")

    data = []
    for offer in offers:
        items = OfferItems.objects.filter(offer=offer).select_related("item")
        item_list = [
            {
                "item_id": item.item.id,
                "item_name": item.item.name,
                "buy_qty": item.buy_qty,
                "offer_qty": item.offer_qty,
                "offer_price": float(item.offer_price or 0),
            }
            for item in items
        ]

        data.append(
            {
                "id": offer.id,
                "name": offer.name,
                "offer_type": offer.offer_type,
                "price": float(offer.price or 0),
                "description": offer.description,
                "start_date": str(offer.start_date),
                "end_date": str(offer.end_date),
                "items": item_list,
            }
        )

    return Response({"status": True, "count": len(data), "offers": data})
