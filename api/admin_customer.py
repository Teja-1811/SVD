from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from milk_agency.models import Customer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_customer_list(request):

    customers = Customer.objects.filter(
        is_superuser=False,   # exclude admin users
        is_staff=False        # optional: exclude staff
    ).order_by('id')

    data = []

    for index, c in enumerate(customers, start=1):
        data.append({
            "id": c.id,
            "serial_no": index,
            "name": c.name,
            "shop_name": c.shop_name or "",
            "phone": c.phone or "",
            "due": float(c.due or 0),
            "frozen": c.frozen
        })

    return Response({
        "customers": data
    })
