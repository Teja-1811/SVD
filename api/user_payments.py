from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from milk_agency.models import (
    AutoUPISetting,
    Customer,
    CustomerPayment,
    CustomerSubscription,
    SubscriptionPause,
)


def _resolve_customer(user_id):
    if not user_id:
        return None, Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        return Customer.objects.get(id=int(user_id)), None
    except (Customer.DoesNotExist, ValueError):
        return None, Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)


def _record_payment(customer, amount, transaction_id, method="UPI", auto=False):
    if amount <= 0:
        raise InvalidOperation

    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        if CustomerPayment.objects.filter(transaction_id=transaction_id).exists():
            raise ValueError("Duplicate transaction")

        CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            transaction_id=transaction_id,
            method=method,
            status="SUCCESS",
        )

        customer.due = customer.get_actual_due()
        customer.save()

        return customer


@api_view(["GET"])
def user_payment_options(request):
    user_id = request.GET.get("user_id")
    customer, error = _resolve_customer(user_id)
    if error:
        return error

    auto_setting = getattr(customer, "auto_upi_setting", None)

    return Response(
        {
            "status": True,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "due": float(customer.get_actual_due() or 0),
            },
            "auto_upi": {
                "is_active": auto_setting.is_active if auto_setting else False,
                "upi_id": auto_setting.upi_id if auto_setting else "",
                "max_amount": float(auto_setting.max_amount) if auto_setting else 0,
                "last_payment_amount": float(auto_setting.last_payment_amount) if auto_setting else 0,
                "last_payment_date": auto_setting.last_payment_date if auto_setting else None,
            },
        }
    )


@api_view(["POST"])
def user_payment_record(request):
    user_id = request.data.get("user_id")
    customer, error = _resolve_customer(user_id)
    if error:
        return error

    try:
        amount = Decimal(str(request.data.get("amount")))
    except (InvalidOperation, TypeError):
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    transaction_id = request.data.get("transaction_id")
    if not transaction_id:
        return Response({"error": "transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    method = request.data.get("method", "UPI").upper()

    try:
        customer = _record_payment(customer, amount, transaction_id, method=method)
    except InvalidOperation:
        return Response({"error": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {"status": "success", "new_balance": str(customer.due)},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def user_auto_upi_toggle(request):
    user_id = request.data.get("user_id")
    customer, error = _resolve_customer(user_id)
    if error:
        return error

    setting, _ = AutoUPISetting.objects.get_or_create(customer=customer)
    setting.upi_id = request.data.get("upi_id", setting.upi_id)
    try:
        max_amount = Decimal(str(request.data.get("max_amount", setting.max_amount)))
        setting.max_amount = max_amount
    except (InvalidOperation, TypeError):
        return Response({"error": "Invalid max_amount"}, status=status.HTTP_400_BAD_REQUEST)

    enabled = request.data.get("enabled")
    if enabled is not None:
        setting.is_active = str(enabled).lower() in ("true", "1", "yes")

    setting.save()

    return Response(
        {
            "status": "success",
            "auto_upi": {
                "is_active": setting.is_active,
                "upi_id": setting.upi_id,
                "max_amount": float(setting.max_amount),
            },
        }
    )


@api_view(["POST"])
def user_auto_upi_pay(request):
    user_id = request.data.get("user_id")
    customer, error = _resolve_customer(user_id)
    if error:
        return error

    setting = getattr(customer, "auto_upi_setting", None)
    if not setting or not setting.is_active:
        return Response({"error": "Auto UPI pay is not enabled"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = Decimal(str(request.data.get("amount")))
    except (InvalidOperation, TypeError):
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    if setting.max_amount and amount > setting.max_amount:
        return Response(
            {"error": "Amount exceeds configured auto pay limit"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    transaction_id = request.data.get("transaction_id")
    if not transaction_id:
        return Response({"error": "transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        customer = _record_payment(customer, amount, transaction_id, method="UPI", auto=True)
    except InvalidOperation:
        return Response({"error": "Amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    setting.last_payment_amount = amount
    setting.last_payment_date = timezone.now()
    setting.save(update_fields=["last_payment_amount", "last_payment_date"])

    return Response(
        {
            "status": "success",
            "auto_upi": {
                "last_payment_amount": float(amount),
                "last_payment_date": setting.last_payment_date,
            },
            "new_balance": str(customer.due),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def user_subscription_pause(request):
    user_id = request.data.get("user_id")
    action = request.data.get("action")
    customer, error = _resolve_customer(user_id)
    if error:
        return error

    if action not in ("pause", "resume"):
        return Response({"error": "action must be 'pause' or 'resume'"}, status=status.HTTP_400_BAD_REQUEST)

    subscription = CustomerSubscription.objects.filter(customer=customer).order_by("-start_date").first()
    if not subscription:
        return Response({"error": "No subscription on record"}, status=status.HTTP_404_NOT_FOUND)

    if action == "pause":
        reason = request.data.get("reason", "Requested by user")
        pause = SubscriptionPause.objects.create(
            subscription=subscription,
            pause_date=timezone.localdate(),
            reason=reason,
        )
        return Response(
            {
                "status": "paused",
                "pause": {
                    "plan": subscription.subscription_plan.name,
                    "pause_date": pause.pause_date,
                    "reason": pause.reason,
                },
            }
        )

    # resume
    pause = (
        SubscriptionPause.objects.filter(subscription=subscription, is_resumed=False)
        .order_by("-pause_date")
        .first()
    )
    if not pause:
        return Response({"error": "No active pause found"}, status=status.HTTP_400_BAD_REQUEST)

    pause.resume()

    return Response(
        {
            "status": "resumed",
            "resume_date": pause.resume_date,
        }
    )
