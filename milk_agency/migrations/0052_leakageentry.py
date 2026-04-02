from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('milk_agency', '0051_rename_milk_agency_date_2fca4d_idx_milk_agency_date_5a35fb_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeakageEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('quantity', models.PositiveIntegerField()),
                ('unit_cost', models.DecimalField(decimal_places=3, max_digits=10)),
                ('total_loss', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leakage_entries', to='milk_agency.item')),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='leakageentry',
            index=models.Index(fields=['date'], name='milk_agency_leakage_date_idx'),
        ),
        migrations.AddIndex(
            model_name='leakageentry',
            index=models.Index(fields=['item'], name='milk_agency_leakage_item_idx'),
        ),
    ]
