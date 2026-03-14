from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone

from milk_agency.models import Offers, OfferItems


@api_view(["GET"])
def user_offers(request):

    today = timezone.localdate()

    offers = Offers.objects.filter(
        offer_for="user",
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    )

    data = []

    for offer in offers:

        items = OfferItems.objects.filter(offer=offer)

        item_list = []

        for i in items:
            item_list.append({
                "item_id": i.item.id,
                "item_name": i.item.name,
                "buy_qty": i.buy_qty,
                "offer_qty": i.offer_qty,
                "offer_price": i.offer_price
            })

        data.append({
            "id": offer.id,
            "name": offer.name,
            "offer_type": offer.offer_type,
            "price": offer.price,
            "description": offer.description,
            "start_date": offer.start_date,
            "end_date": offer.end_date,
            "items": item_list
        })

    return Response({
        "status": True,
        "offers": data
    })