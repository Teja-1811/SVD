from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0045_subscriptiondelivery_bill"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("resolved", "Resolved")],
                default="active",
                max_length=20,
            ),
        ),
    ]
