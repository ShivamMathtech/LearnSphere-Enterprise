"""Disposable browser-test server. Never touches the user's development database."""
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
temporary = tempfile.TemporaryDirectory(prefix='learnsphere-e2e-')
os.environ.update(APP_ENV='development', DATABASE_URL='sqlite:///' + str(Path(temporary.name) / 'e2e.db'), STORAGE_PATH=str(Path(temporary.name) / 'storage'), DEMO_ENABLED='true', EMAIL_VERIFICATION_REQUIRED='false', REQUIRE_PRIVILEGED_MFA='false')
os.chdir(root / 'backend')
sys.path.insert(0, str(root / 'backend'))
from alembic import command
from alembic.config import Config
from app.cli import seed_demo
import uvicorn
command.upgrade(Config('alembic.ini'), 'head')
seed_demo()
uvicorn.run('app.main:app', host='127.0.0.1', port=8000, access_log=False)
