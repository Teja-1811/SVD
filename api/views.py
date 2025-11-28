from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def login_api(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    user = authenticate(request, username=phone, password=password)

    if user is None:
        return Response({"status": "error", "message": "Invalid phone or password"}, status=400)

    return Response({
        "status": "success",
        "phone": user.phone,
        "name": user.get_full_name() if hasattr(user, "get_full_name") else "",
    })
