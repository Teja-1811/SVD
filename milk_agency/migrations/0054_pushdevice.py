from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0053_rename_milk_agency_leakage_date_idx_milk_agency_date_10a8b6_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.TextField(unique=True)),
                ("device_type", models.CharField(choices=[("web", "Web")], default="web", max_length=20)),
                ("user_agent", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="push_devices", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-last_seen_at", "-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["customer", "is_active"], name="milk_agency_customer_7b3f55_idx"),
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["last_seen_at"], name="milk_agency_last_se_7b4cfd_idx"),
        ),
    ]
