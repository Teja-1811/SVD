from django.contrib.auth import authenticate
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def login_api(request):
    print("RAW DATA:", request.data)   # DEBUG

    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response({"status":"error","message":"Phone and password required"}, status=400)

    user = authenticate(request, username=phone, password=password)
    print("AUTH RESULT:", user)         # DEBUG

    if user is None:
        return Response({"status":"error","message":"Invalid phone or password"}, status=400)

    return Response({
        "status": "success",
        "phone": user.phone,
        "name": user.name,
    })
