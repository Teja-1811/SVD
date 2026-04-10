from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customer_portal", "0013_customergatewaypayment"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerorder",
            name="gateway_order_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Gateway-specific order id used for payment initiation",
                max_length=64,
            ),
        ),
    ]
