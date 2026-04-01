from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0048_merge_20260324_1328"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockInEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=django.utils.timezone.localdate)),
                ("crates", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("quantity", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_in_entries", to="milk_agency.company")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_in_entries", to="milk_agency.item")),
            ],
            options={
                "ordering": ["-date", "-created_at"],
                "indexes": [
                    models.Index(fields=["date"], name="milk_agency_date_2fca4d_idx"),
                    models.Index(fields=["company"], name="milk_agency_company_ee3748_idx"),
                ],
            },
        ),
    ]
