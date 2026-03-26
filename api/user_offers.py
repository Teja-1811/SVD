from rest_framework.decorators import api_view
from rest_framework.response import Response

from .user_api_helpers import get_active_offers


def get_active_user_offers():
    return get_active_offers(offer_for="user")


@api_view(["GET"])
def user_offers(request):
    return Response(
        {
            "status": True,
            "offers": get_active_user_offers(),
        }
    )
