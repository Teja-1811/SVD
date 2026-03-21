from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Contact


def _serialize_enquiry(contact: Contact):
    return {
        "id": contact.id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email or "",
        "subject": contact.subject,
        "message": contact.message,
        "status": contact.status,
        "created_at": contact.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@api_view(["GET"])
def api_active_enquiries(request):
    enquiries = Contact.objects.filter(status="active").order_by("-created_at")
    data = [_serialize_enquiry(enquiry) for enquiry in enquiries]

    return Response({
        "success": True,
        "count": len(data),
        "enquiries": data,
    })


@api_view(["GET"])
def api_resolved_enquiries(request):
    enquiries = Contact.objects.filter(status="resolved").order_by("-created_at")
    data = [_serialize_enquiry(enquiry) for enquiry in enquiries]

    return Response({
        "success": True,
        "count": len(data),
        "enquiries": data,
    })


@api_view(["POST"])
def api_update_enquiry_status(request, enquiry_id):
    enquiry = get_object_or_404(Contact, id=enquiry_id)
    new_status = str(request.data.get("status", "")).strip().lower()

    allowed_statuses = {choice[0] for choice in Contact.STATUS_CHOICES}
    if new_status not in allowed_statuses:
        return Response({
            "success": False,
            "message": "Valid status is required.",
            "allowed_statuses": sorted(allowed_statuses),
        }, status=400)

    enquiry.status = new_status
    enquiry.save(update_fields=["status"])

    return Response({
        "success": True,
        "message": "Enquiry status updated successfully.",
        "enquiry": _serialize_enquiry(enquiry),
    })
