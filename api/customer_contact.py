from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from milk_agency.models import Contact


def _serialize_contact_ticket(contact: Contact):
    return {
        "id": contact.id,
        "customer_id": contact.customer_id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email or "",
        "subject": contact.subject,
        "message": contact.message,
        "status": contact.status,
        "created_at": contact.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_support_ticket_summary(request):
    customer_contacts = Contact.objects.filter(customer=request.user)
    raised_tickets = customer_contacts.filter(status="active").count()
    resolved_tickets = customer_contacts.filter(status="resolved").count()
    latest_ticket = customer_contacts.order_by("-created_at").first()

    return Response(
        {
            "success": True,
            "raised_tickets": raised_tickets,
            "resolved_tickets": resolved_tickets,
            "total_tickets": raised_tickets + resolved_tickets,
            "latest_ticket": _serialize_contact_ticket(latest_ticket) if latest_ticket else None,
        }
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_raised_queries_api(request):
    customer_contacts = Contact.objects.filter(customer=request.user).order_by("-created_at")
    data = [_serialize_contact_ticket(contact) for contact in customer_contacts]

    return Response(
        {
            "success": True,
            "count": len(data),
            "active_count": sum(1 for row in data if row["status"] == "active"),
            "resolved_count": sum(1 for row in data if row["status"] == "resolved"),
            "queries": data,
        }
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_contact_api(request):
    name = str(request.data.get("name", "")).strip()
    phone = str(request.data.get("phone", "")).strip()
    email = str(request.data.get("email", "")).strip()
    subject = str(request.data.get("subject", "")).strip()
    message = str(request.data.get("message", "")).strip()

    if not all([name, phone, subject, message]):
        return Response({"success": False, "message": "Please fill all required fields."}, status=400)

    contact = Contact.objects.create(
        customer=request.user,
        name=name,
        phone=phone,
        email=email or None,
        subject=subject,
        message=message,
    )

    return Response(
        {
            "success": True,
            "message": "Thank you! We will contact you soon.",
            "contact_id": contact.id,
            "status": contact.status,
        }
    )
