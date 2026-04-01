from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0049_stockinentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="buying_price",
            field=models.DecimalField(decimal_places=3, max_digits=10),
        ),
        migrations.AlterField(
            model_name="item",
            name="selling_price",
            field=models.DecimalField(decimal_places=3, max_digits=10),
        ),
        migrations.AlterField(
            model_name="item",
            name="mrp",
            field=models.DecimalField(decimal_places=3, default=0, help_text="Maximum Retail Price", max_digits=10),
        ),
    ]
