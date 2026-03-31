from django.shortcuts import render

from .helpers import offers_context, user_required


@user_required
def offers_page(request):
    return render(
        request,
        "user_portal/offers.html",
        {"offers": offers_context()},
    )
