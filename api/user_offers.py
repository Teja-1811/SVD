from rest_framework.decorators import api_view
from rest_framework.response import Response

from users.helpers import offers_context


def get_active_user_offers():
    return offers_context()


@api_view(["GET"])
def user_offers(request):
    return Response(
        {
            "status": True,
            "offers": get_active_user_offers(),
        }
    )
