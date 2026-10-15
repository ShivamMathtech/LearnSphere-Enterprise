"""Usage: python scripts/sqlite-backup.py [destination.db]"""
import datetime
from pathlib import Path
import sqlite3
import sys
root = Path(__file__).resolve().parents[1]
source = root / 'backend/data/learnsphere.db'
destination = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'backups' / ('learnsphere-' + datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%S') + '.db')
if not source.is_file():
    raise SystemExit('Default SQLite database does not exist')
if destination.exists():
    raise SystemExit('Destination exists; refusing to overwrite a backup')
destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source) as src, sqlite3.connect(destination) as dest:
    src.backup(dest)
print(destination.resolve())
print('Also copy backend/storage and preserve the encryption key in secure secret storage.')
