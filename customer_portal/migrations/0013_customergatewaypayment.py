from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0053_rename_milk_agency_leakage_date_idx_milk_agency_date_10a8b6_idx_and_more"),
        ("customer_portal", "0012_customerorder_payment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerGatewayPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_order_id", models.CharField(max_length=64, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("gateway", models.CharField(default="PAYTM", max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("gateway_transaction_id", models.CharField(blank=True, default="", max_length=120)),
                ("callback_payload", models.JSONField(blank=True, default=dict)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bill",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gateway_payments",
                        to="milk_agency.bill",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="customer_gateway_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
