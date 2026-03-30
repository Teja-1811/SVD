from django.db import migrations


MYSQL_FORWARD_SQL = """
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

MYSQL_REVERSE_SQL = """
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


def forward_fix_delivery_date(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    for statement in [part.strip() for part in MYSQL_FORWARD_SQL.split(';') if part.strip()]:
        schema_editor.execute(statement)


def reverse_fix_delivery_date(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    for statement in [part.strip() for part in MYSQL_REVERSE_SQL.split(';') if part.strip()]:
        schema_editor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [
        ('customer_portal', '0009_customerorder_delivery_charge_and_more'),
    ]

    operations = [
        migrations.RunPython(forward_fix_delivery_date, reverse_fix_delivery_date),
    ]
