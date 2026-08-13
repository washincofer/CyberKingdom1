import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from cyberkingdoms.db import Database


class SchemaTests(unittest.TestCase):
    def test_seed_and_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "db.sqlite")
            db.initialize()
            with db.transaction() as conn:
                self.assertEqual("1", conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
                self.assertEqual(50, conn.execute("SELECT available_qty FROM market_listings WHERE id='lst-ration-basic'").fetchone()[0])
                self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM financial_accounts").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
