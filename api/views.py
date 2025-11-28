from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

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

    return Response({
        "status": "success",
        "phone": user.phone,
        "name": user.name,
        "token": token.key
    })
