from decimal import Decimal

from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from api.user_api_helpers import find_linked_order_for_bill, get_delivery_charge_for_bill
from milk_agency.models import Bill

from .helpers import user_required


@user_required
def invoices_page(request):
    selected_month = request.GET.get("date", timezone.now().strftime("%Y-%m"))
    try:
        year, month = map(int, selected_month.split("-"))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    bills = Bill.objects.filter(
        customer=request.user,
        is_deleted=False,
        invoice_date__year=year,
        invoice_date__month=month,
    ).order_by("-invoice_date", "-id")

    total_amount = sum(Decimal(b.total_amount or 0) for b in bills)
    average_amount = (total_amount / bills.count()) if bills else Decimal("0.00")

    return render(
        request,
        "user_portal/invoices.html",
        {
            "bills": bills,
            "selected_date": selected_month,
            "current_year": year,
            "current_month": month,
            "total_amount": total_amount,
            "average_amount": average_amount,
        },
    )


@user_required
def invoice_detail(request, bill_id):
    bill = get_object_or_404(
        Bill.objects.select_related("customer").filter(
            customer=request.user,
            is_deleted=False,
        ),
        id=bill_id,
    )
    bill_items = list(bill.items.all().select_related("item"))
    linked_order = find_linked_order_for_bill(request.user, bill)
    delivery_charge = Decimal(
        get_delivery_charge_for_bill(bill, bill_items=bill_items, linked_order=linked_order)
    )
    display_items = [
        item for item in bill_items if getattr(item.item, "code", "") != "DELIVERY_CHARGE"
    ]

    return render(
        request,
        "user_portal/invoice_detail.html",
        {
            "bill": bill,
            "bill_items": display_items,
            "delivery_charge": delivery_charge,
            "items_subtotal": Decimal(bill.total_amount or 0) - delivery_charge,
        },
    )
