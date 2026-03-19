from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0044_orderdelivery_subscriptiondelivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptiondelivery",
            name="bill",
            field=models.ForeignKey(
                blank=True,
                help_text="Bill generated for this subscription delivery",
                null=True,
                on_delete=models.SET_NULL,
                related_name="subscription_deliveries",
                to="milk_agency.bill",
            ),
        ),
    ]
