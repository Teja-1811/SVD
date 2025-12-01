from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

def get_user_role(user):
    if user.is_superuser:
        return "admin"
    if getattr(user, "is_delivery", False):
        return "delivery"
    return "customer"

@api_view(['POST'])
def login_api(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response({"status": "error", "message": "Phone and password required"}, status=400)

    user = authenticate(request, username=phone, password=password)

    if user is None:
        return Response({"status": "error", "message": "Invalid phone or password"}, status=400)

    token, created = Token.objects.get_or_create(user=user)

    # Determine role
    role = get_user_role(user)

    return Response({
        "status": "success",
        "phone": user.phone,
        "name": user.name,
        "role": role,
        "user_id": user.id,
        "token": token.key
    })
