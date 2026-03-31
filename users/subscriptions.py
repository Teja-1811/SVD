from django.shortcuts import render

from .helpers import subscription_context, user_required


@user_required
def subscriptions_page(request):
    subscription, items = subscription_context(request.user)
    return render(
        request,
        "user_portal/subscriptions.html",
        {
            "subscription": subscription,
            "subscription_items": items,
        },
    )
