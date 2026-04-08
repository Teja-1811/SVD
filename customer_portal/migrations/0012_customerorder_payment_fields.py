from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0053_rename_milk_agency_leakage_date_idx_milk_agency_date_10a8b6_idx_and_more"),
        ("customer_portal", "0011_alter_customerorder_delivery_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerorder",
            name="bill",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="linked_orders",
                to="milk_agency.bill",
            ),
        ),
        migrations.AddField(
            model_name="customerorder",
            name="payment_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customerorder",
            name="payment_method",
            field=models.CharField(blank=True, default="", help_text="Payment method selected by customer", max_length=20),
        ),
        migrations.AddField(
            model_name="customerorder",
            name="payment_reference",
            field=models.CharField(blank=True, default="", help_text="Gateway payment reference / transaction id", max_length=120),
        ),
        migrations.AddField(
            model_name="customerorder",
            name="payment_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="customerorder",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="customerorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("payment_pending", "Payment Pending"),
                    ("pending", "Pending Review"),
                    ("confirmed", "Confirmed"),
                    ("cancelled", "Cancelled"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
