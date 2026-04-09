from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("milk_agency", "0054_pushdevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="pushdevice",
            name="app_version",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="pushdevice",
            name="device_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="pushdevice",
            name="device_type",
            field=models.CharField(choices=[("web", "Web"), ("android", "Android")], default="web", max_length=20),
        ),
    ]
