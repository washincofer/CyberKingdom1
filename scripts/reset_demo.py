import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from cyberkingdoms.api import DEFAULT_DB
from cyberkingdoms.db import Database
Database(DEFAULT_DB).reset()
print(f"Demo reset: {DEFAULT_DB}")
