from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0057_customerpayment_callback_payload_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpayment",
            name="callback_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="userpayment",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userpayment",
            name="gateway",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="userpayment",
            name="gateway_transaction_id",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="userpayment",
            name="payment_order_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
