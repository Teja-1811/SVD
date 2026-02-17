from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db.models import (
    Sum, Max, F, ExpressionWrapper, DecimalField
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from milk_agency.models import (
    CashbookEntry,
    Expense,
    BankBalance,
    DailyPayment,
    Customer,
    Bill,
    Item
)


# ======================================================
# 1️⃣ CASHBOOK DASHBOARD
# ======================================================
@api_view(['GET'])
def api_cashbook_dashboard(request):

    today = timezone.now().date()

    # ---- Month & Year filter ----
    try:
        month = int(request.GET.get("month", today.month))
        year = int(request.GET.get("year", today.year))
    except ValueError:
        return Response({"error": "Invalid month or year"}, status=400)

    # ---- Cash Entry ----
    cash_entry = CashbookEntry.objects.first()
    if not cash_entry:
        cash_entry = CashbookEntry.objects.create()

    # ---- Cash In ----
    cash_in = (
        cash_entry.c500 * 500 +
        cash_entry.c200 * 200 +
        cash_entry.c100 * 100 +
        cash_entry.c50 * 50 +
        cash_entry.c20 * 20 +
        cash_entry.c10 * 10
    )

    denominations = {
        "c500": cash_entry.c500,
        "c200": cash_entry.c200,
        "c100": cash_entry.c100,
        "c50": cash_entry.c50,
        "c20": cash_entry.c20,
        "c10": cash_entry.c10,
    }

    # ---- Cash Out (Expenses) ----
    expenses = Expense.objects.filter(
        date__year=year,
        date__month=month
    )

    total_cash_out = expenses.aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )["total"]

    # ---- Bank Balance (latest entry) ----
    bank_balance_obj = BankBalance.objects.order_by("-date").first()
    bank_balance = bank_balance_obj.amount if bank_balance_obj else Decimal("0.00")

    # ---- Company Dues ----
    company_dues = DailyPayment.objects.filter(
        date__year=year,
        date__month=month
    ).values(
        company_name=F("company__name")
    ).annotate(
        total_invoice=Coalesce(
            Sum("invoice_amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        total_paid=Coalesce(
            Sum("paid_amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        total_due=ExpressionWrapper(
            F("total_invoice") - F("total_paid"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        last_updated=Max("date")
    )

    company_dues = [c for c in company_dues if c["total_due"] != 0]
    total_company_dues = sum(c["total_due"] for c in company_dues) or Decimal("0.00")

    # ---- Customer Dues (cached total) ----
    total_customer_dues = Customer.objects.aggregate(
        total=Coalesce(
            Sum("due"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )["total"]

    # ---- Monthly Profit (exclude soft-deleted bills) ----
    monthly_profit = Bill.objects.filter(
        is_deleted=False,
        invoice_date__year=year,
        invoice_date__month=month
    ).aggregate(
        profit=Coalesce(
            Sum("profit"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )["profit"]

    # ---- Net Calculations ----
    net_profit = monthly_profit - total_cash_out
    net_cash = cash_in + bank_balance + total_customer_dues

    # ---- Stock Value ----
    stock_value = Item.objects.aggregate(
        total=Coalesce(
            Sum(F("stock_quantity") * F("buying_price")),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )["total"]

    remaining_amount = (
        net_cash + stock_value - net_profit - total_company_dues
    )

    return Response({
        "date": str(today),
        "month": month,
        "year": year,
        "cash_in": cash_in,
        "denominations": denominations,
        "cash_out": total_cash_out,
        "bank_balance": bank_balance,
        "company_dues": company_dues,
        "total_company_dues": total_company_dues,
        "total_customer_dues": total_customer_dues,
        "monthly_profit": monthly_profit,
        "net_profit": net_profit,
        "net_cash": net_cash,
        "stock_value": stock_value,
        "remaining_amount": remaining_amount
    })


# ======================================================
# 2️⃣ SAVE / UPDATE CASH IN
# ======================================================
@api_view(['POST'])
def api_save_cash_in(request):

    cash_entry = CashbookEntry.objects.first()
    if not cash_entry:
        cash_entry = CashbookEntry.objects.create()

    fields = ["c500", "c200", "c100", "c50", "c20", "c10"]

    for field in fields:
        setattr(cash_entry, field, int(request.data.get(field, 0)))

    cash_entry.save()
    return Response({"success": True})


# ======================================================
# 3️⃣ ADD EXPENSE
# ======================================================
@api_view(['POST'])
def api_add_expense(request):

    try:
        Expense.objects.create(
            amount=Decimal(request.data.get("amount")),
            category=request.data.get("category"),
            description=request.data.get("description", "")
        )
        return Response({"success": True})
    except Exception:
        return Response({"error": "Invalid expense data"}, status=400)


# ======================================================
# 4️⃣ LIST EXPENSES
# ======================================================
@api_view(['GET'])
def api_list_expenses(request):

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    expenses = Expense.objects.all()

    if start_date and end_date:
        expenses = expenses.filter(date__range=[start_date, end_date])

    expenses = expenses.order_by("-date")

    total = expenses.aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )["total"]

    return Response({
        "expenses": [
            {
                "id": e.id,
                "date": str(e.date),
                "category": e.category,
                "amount": float(e.amount),
                "description": e.description
            } for e in expenses
        ],
        "total_expenses": total
    })


# ======================================================
# 5️⃣ EDIT EXPENSE
# ======================================================
@api_view(['PUT'])
def api_edit_expense(request, expense_id):

    expense = Expense.objects.filter(id=expense_id).first()
    if not expense:
        return Response({"error": "Expense not found"}, status=404)

    try:
        expense.amount = Decimal(request.data.get("amount"))
        expense.category = request.data.get("category")
        expense.description = request.data.get("description", "")
        expense.save()
        return Response({"success": True})
    except Exception:
        return Response({"error": "Invalid expense data"}, status=400)


# ======================================================
# 6️⃣ DELETE EXPENSE
# ======================================================
@api_view(['DELETE'])
def api_delete_expense(request, expense_id):

    expense = Expense.objects.filter(id=expense_id).first()
    if not expense:
        return Response({"error": "Expense not found"}, status=404)

    expense.delete()
    return Response({"success": True})


# ======================================================
# 7️⃣ SAVE BANK BALANCE (history-aware)
# ======================================================
@api_view(['POST'])
def api_save_bank_balance(request):

    try:
        amount = Decimal(request.data.get("amount"))
        BankBalance.objects.create(amount=amount)  # preserve history
        return Response({"success": True})
    except Exception:
        return Response({"error": "Invalid amount"}, status=400)
