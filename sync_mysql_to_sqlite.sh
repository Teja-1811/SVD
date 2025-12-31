#!/bin/bash

PROJECT_DIR="/home/ubuntu/SVD"
PYTHON="$PROJECT_DIR/venv/bin/python"
SQLITE_DB="$PROJECT_DIR/db.sqlite3"
DUMP_FILE="$PROJECT_DIR/mysql_dump.json"

cd "$PROJECT_DIR" || exit

echo "==== MySQL → SQLite Sync Started $(date) ===="

# 1. Dump MySQL data
$PYTHON manage.py dumpdata --natural-foreign --natural-primary > "$DUMP_FILE"
if [ $? -ne 0 ]; then
  echo "❌ dumpdata failed"
  exit 1
fi

# 2. Remove old sqlite database
rm -f "$SQLITE_DB"

# 3. Recreate schema in SQLite
$PYTHON manage.py migrate
if [ $? -ne 0 ]; then
  echo "❌ migrate failed"
  exit 1
fi

# 4. Load MySQL dump into SQLite
$PYTHON manage.py loaddata "$DUMP_FILE"
if [ $? -ne 0 ]; then
  echo "❌ loaddata failed"
  exit 1
fi

echo "==== Sync Completed Successfully $(date) ===="
