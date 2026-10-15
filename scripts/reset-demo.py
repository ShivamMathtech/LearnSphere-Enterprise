"""Explicit development reset. Backs up the SQLite file before changing anything."""
from pathlib import Path
import datetime
import os
import sqlite3
import sys
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / 'backend')
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.config import settings
from app.db.session import engine
from app.cli import seed_demo

s = settings()
if '--confirmed' not in sys.argv or s.production or not s.demo_enabled or s.database_url != 'sqlite:///./data/learnsphere.db':
    raise SystemExit('Reset refused. Only the confirmed, default SQLite development database is supported.')
if input('Stop ALL application processes first. Type STOPPED to confirm: ') != 'STOPPED':
    raise SystemExit('Cancelled')
engine.dispose()
path = Path('data/learnsphere.db')
if path.exists():
    backup = ROOT / 'backups' / ('demo-' + datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%S') + '.db')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    path.unlink()
    for suffix in ('-wal', '-shm'):
        Path(str(path) + suffix).unlink(missing_ok=True)
    print('Previous database backed up:', backup)
command.upgrade(Config('alembic.ini'), 'head')
seed_demo()
print('New development database created. Previous uploaded bytes are retained for recovery.')
