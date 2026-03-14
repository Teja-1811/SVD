from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Offers, OfferItems, Item


@login_required
def offers_dashboard(request):

    offers = Offers.objects.all().order_by("-id")
    items = Item.objects.all()

    return render(
        request,
        "milk_agency/dashboards_other/offers_dashboard.html",
        {
            "offers": offers,
            "items": items
        }
    )


# CREATE OFFER
@login_required
def create_offer(request):

    if request.method == "POST":

        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        offer_for = request.POST.get("offer_for")

        if not name or not price:
            messages.error(request, "Offer name and price required")
            return redirect("milk_agency:offers_dashboard")

        Offers.objects.create(
            name=name,
            description=description,
            price=price,
            offer_for=offer_for
        )

        messages.success(request, "Offer created successfully")

    return redirect("milk_agency:offers_dashboard")


# UPDATE OFFER
@login_required
def update_offer(request, offer_id):

    offer = get_object_or_404(Offers, id=offer_id)

    if request.method == "POST":

        offer.name = request.POST.get("name")
        offer.description = request.POST.get("description")
        offer.price = request.POST.get("price")

        offer.save()

        messages.success(request, "Offer updated successfully")

    return redirect("milk_agency:offers_dashboard")


# DELETE OFFER
@login_required
def delete_offer(request, offer_id):

    offer = get_object_or_404(Offers, id=offer_id)

    offer.delete()

    messages.success(request, "Offer deleted")

    return redirect("milk_agency:offers_dashboard")


# ADD OFFER ITEM
@login_required
def add_offer_item(request, offer_id):

    offer = get_object_or_404(Offers, id=offer_id)

    if request.method == "POST":

        item = request.POST.get("item")
        buy_qty = request.POST.get("buy_qty")
        offer_qty = request.POST.get("offer_qty")
        offer_price = request.POST.get("offer_price")

        OfferItems.objects.create(
            offer=offer,
            item_id=item,
            buy_qty=buy_qty,
            offer_qty=offer_qty,
            offer_price=offer_price
        )

        messages.success(request, "Offer item added")

    return redirect("milk_agency:offers_dashboard")


# UPDATE OFFER ITEM
@login_required
def update_offer_item(request, item_id):

    item = get_object_or_404(OfferItems, id=item_id)

    if request.method == "POST":

        item.buy_qty = request.POST.get("buy_qty")
        item.offer_qty = request.POST.get("offer_qty")
        item.offer_price = request.POST.get("offer_price")

        item.save()

        messages.success(request, "Offer item updated")

    return redirect("milk_agency:offers_dashboard")


# DELETE OFFER ITEM
@login_required
def delete_offer_item(request, item_id):

    item = get_object_or_404(OfferItems, id=item_id)

    item.delete()

    messages.success(request, "Offer item deleted")

    return redirect("milk_agency:offers_dashboard")