#!/bin/bash

PROJECT_DIR="/home/ubuntu/SVD"
PYTHON="$PROJECT_DIR/venv/bin/python"

cd $PROJECT_DIR || exit

echo "Starting sync: $(date)"

# Export MySQL → JSON
$PYTHON manage.py dumpdata --natural-foreign --natural-primary > mysql_dump.json

# Remove old sqlite
rm -f db.sqlite3

# Re-create SQLite schema
$PYTHON manage.py migrate

# Load data into sqlite
$PYTHON manage.py loaddata mysql_dump.json

echo "Sync completed: $(date)"
