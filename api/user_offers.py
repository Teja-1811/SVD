from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone

from milk_agency.models import Offers


def get_active_user_offers():
    today = timezone.localdate()
    offers = Offers.objects.filter(
        offer_for="user",
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    ).prefetch_related("offeritems_set__item")

    serialized = []
    for offer in offers:
        item_list = []
        for item in offer.offeritems_set.select_related("item").all():
            item_list.append({
                "item_id": item.item.id,
                "item_name": item.item.name,
                "buy_qty": item.buy_qty,
                "offer_qty": item.offer_qty,
                "offer_price": item.offer_price,
            })

        serialized.append({
            "id": offer.id,
            "name": offer.name,
            "offer_type": offer.offer_type,
            "price": offer.price,
            "description": offer.description,
            "start_date": offer.start_date,
            "end_date": offer.end_date,
            "items": item_list,
        })

    return serialized


@api_view(["GET"])
def user_offers(request):
    return Response({
        "status": True,
        "offers": get_active_user_offers(),
    })
