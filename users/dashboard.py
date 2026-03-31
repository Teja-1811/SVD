from django.shortcuts import render

from .helpers import dashboard_cards, user_required


@user_required
def dashboard(request):
    context = dashboard_cards(request.user)
    return render(request, "user_portal/dashboard.html", context)
