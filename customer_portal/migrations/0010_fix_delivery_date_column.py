from django.db import migrations


RENAME_SQL = """
SET @col := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'customer_portal_customerorder'
      AND COLUMN_NAME = 'devivery_date'
);
SET @q := IF(@col > 0,
    'ALTER TABLE customer_portal_customerorder CHANGE devivery_date delivery_date date NULL',
    'SELECT 1'
);
PREPARE stmt FROM @q;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
"""

REVERSE_SQL = """
SET @col := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'customer_portal_customerorder'
      AND COLUMN_NAME = 'delivery_date'
);
SET @q := IF(@col > 0,
    'ALTER TABLE customer_portal_customerorder CHANGE delivery_date devivery_date date NULL',
    'SELECT 1'
);
PREPARE stmt FROM @q;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('customer_portal', '0009_customerorder_delivery_charge_and_more'),
    ]

    operations = [
        migrations.RunSQL(sql=RENAME_SQL, reverse_sql=REVERSE_SQL),
    ]
