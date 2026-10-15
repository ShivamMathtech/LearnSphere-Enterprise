from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / 'backend')
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.config import settings
from app.cli import seed_demo
if settings().demo_enabled and not settings().production:
    seed_demo()
else:
    print('Demo seed is disabled. Use the secure bootstrap command to create your administrator.')
