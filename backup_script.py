import os
from datetime import datetime

# Paths
BASE_DIR = "/home/ubuntu/SVD"
BACKUP_DIR = f"{BASE_DIR}/db_backups"
DB_PATH = f"{BASE_DIR}/db.sqlite3"

# Create backup directory if not exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# Backup filename
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file = f"{BACKUP_DIR}/backup_{timestamp}.sqlite3"

# Copy database
os.system(f"cp {DB_PATH} {backup_file}")

print(f"Backup created: {backup_file}")
