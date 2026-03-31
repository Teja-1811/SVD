from django.shortcuts import render

from .helpers import (
    active_orders,
    grouped_catalog,
    minimum_prebook_date,
    save_user_order_response,
    user_required,
)


@user_required
def orders_page(request):
    return render(
        request,
        "user_portal/orders.html",
        {
            "available_items_by_category": grouped_catalog(request.user, include_out_of_stock=False),
            "prebook_items_by_category": grouped_catalog(request.user, include_out_of_stock=True),
            "active_orders": active_orders(request.user),
            "min_prebooking_date": minimum_prebook_date(),
        },
    )


@user_required
def place_order(request):
    return save_user_order_response(request)
