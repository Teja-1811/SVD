from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Item, OfferItems, Offers


def _serialize_offer_item(offer_item):
    return {
        "id": offer_item.id,
        "item_id": offer_item.item_id,
        "item_name": offer_item.item.name if offer_item.item else None,
        "buy_qty": offer_item.buy_qty,
        "offer_qty": offer_item.offer_qty,
        "offer_price": float(offer_item.offer_price),
    }


def _serialize_offer(offer):
    return {
        "id": offer.id,
        "name": offer.name,
        "offer_for": offer.offer_for,
        "offer_type": offer.offer_type,
        "price": float(offer.price),
        "description": offer.description,
        "start_date": str(offer.start_date),
        "end_date": str(offer.end_date),
        "is_active": offer.is_active,
        "items": [_serialize_offer_item(item) for item in offer.offeritems_set.select_related("item").all()],
    }


@api_view(["GET"])
def api_offers_dashboard(request):
    offers = Offers.objects.all().prefetch_related("offeritems_set__item").order_by("-id")
    items = Item.objects.filter(frozen=False).order_by("name")

    return Response({
        "offers": [_serialize_offer(offer) for offer in offers],
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "company_name": item.company.name if item.company else None,
                "stock_quantity": item.stock_quantity,
            }
            for item in items
        ],
    })


@api_view(["POST"])
def api_create_offer(request):
    name = request.data.get("name")
    description = request.data.get("description")
    price = request.data.get("price")
    offer_for = request.data.get("offer_for")
    offer_type = request.data.get("offer_type", "bundle")
    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")

    if not name or price is None or not offer_for or not start_date or not end_date:
        return Response({"success": False, "message": "name, price, offer_for, start_date and end_date are required"}, status=400)

    try:
        price = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError):
        return Response({"success": False, "message": "Invalid price"}, status=400)

    offer = Offers.objects.create(
        name=name,
        description=description,
        price=price,
        offer_for=offer_for,
        offer_type=offer_type,
        start_date=start_date,
        end_date=end_date,
    )

    return Response({"success": True, "message": "Offer created successfully", "offer": _serialize_offer(offer)})


@api_view(["POST", "PUT"])
def api_update_offer(request, offer_id):
    offer = get_object_or_404(Offers, id=offer_id)

    if request.data.get("name") is not None:
        offer.name = request.data.get("name")
    if request.data.get("description") is not None:
        offer.description = request.data.get("description")
    if request.data.get("price") is not None:
        try:
            offer.price = Decimal(str(request.data.get("price")))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"success": False, "message": "Invalid price"}, status=400)
    if request.data.get("offer_for") is not None:
        offer.offer_for = request.data.get("offer_for")
    if request.data.get("offer_type") is not None:
        offer.offer_type = request.data.get("offer_type")
    if request.data.get("start_date") is not None:
        offer.start_date = request.data.get("start_date")
    if request.data.get("end_date") is not None:
        offer.end_date = request.data.get("end_date")
    if request.data.get("is_active") is not None:
        offer.is_active = str(request.data.get("is_active")).lower() in ("1", "true", "yes", "on")

    offer.save()
    return Response({"success": True, "message": "Offer updated successfully", "offer": _serialize_offer(offer)})


@api_view(["DELETE", "POST"])
def api_delete_offer(request, offer_id):
    offer = get_object_or_404(Offers, id=offer_id)
    offer.delete()
    return Response({"success": True, "message": "Offer deleted"})


@api_view(["POST"])
def api_add_offer_item(request, offer_id):
    offer = get_object_or_404(Offers, id=offer_id)
    item_id = request.data.get("item")
    buy_qty = request.data.get("buy_qty", 0)
    offer_qty = request.data.get("offer_qty", 0)
    offer_price = request.data.get("offer_price", 0)

    if not item_id:
        return Response({"success": False, "message": "item is required"}, status=400)

    try:
        offer_price = Decimal(str(offer_price or 0))
        buy_qty = int(buy_qty or 0)
        offer_qty = int(offer_qty or 0)
    except (InvalidOperation, TypeError, ValueError):
        return Response({"success": False, "message": "Invalid offer item values"}, status=400)

    offer_item = OfferItems.objects.create(
        offer=offer,
        item_id=item_id,
        buy_qty=buy_qty,
        offer_qty=offer_qty,
        offer_price=offer_price,
    )

    return Response({"success": True, "message": "Offer item added", "offer_item": _serialize_offer_item(offer_item)})


@api_view(["POST", "PUT"])
def api_update_offer_item(request, item_id):
    offer_item = get_object_or_404(OfferItems.objects.select_related("item"), id=item_id)

    try:
        if request.data.get("buy_qty") is not None:
            offer_item.buy_qty = int(request.data.get("buy_qty") or 0)
        if request.data.get("offer_qty") is not None:
            offer_item.offer_qty = int(request.data.get("offer_qty") or 0)
        if request.data.get("offer_price") is not None:
            offer_item.offer_price = Decimal(str(request.data.get("offer_price") or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Response({"success": False, "message": "Invalid offer item values"}, status=400)

    offer_item.save()
    return Response({"success": True, "message": "Offer item updated", "offer_item": _serialize_offer_item(offer_item)})


@api_view(["DELETE", "POST"])
def api_delete_offer_item(request, item_id):
    offer_item = get_object_or_404(OfferItems, id=item_id)
    offer_item.delete()
    return Response({"success": True, "message": "Offer item deleted"})
