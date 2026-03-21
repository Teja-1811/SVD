from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0046_contact_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="contact_tickets",
                to="milk_agency.customer",
            ),
        ),
    ]
