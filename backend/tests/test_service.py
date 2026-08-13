import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from cyberkingdoms.db import Database
from cyberkingdoms.errors import ApiError
from cyberkingdoms.service import GameService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        self.svc = GameService(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def work_and_settle(self):
        result = self.svc.queue_public_work("work-1", 1)
        time.sleep(1.05)
        self.svc.reconcile()
        return result

    def test_health(self):
        self.assertEqual("sqlite", self.svc.health()["database"])

    def test_full_vs001_journey(self):
        self.work_and_settle()
        self.assertEqual(50, self.svc.balance("fa-player")["balance"])
        purchase = self.svc.purchase("lst-ration-basic", 1, "buy-1")
        self.assertEqual(20, purchase["total_cz"])
        self.assertEqual(30, self.svc.balance("fa-player")["balance"])
        self.assertEqual(1, self.svc.inventory("inv-player")["items"]["RATION_BASIC"])
        result = self.svc.consume("RATION_BASIC", 1, "eat-1")
        self.assertGreaterEqual(result["vitals"]["hunger"], 70)
        self.assertEqual(0, self.svc.inventory("inv-player")["items"]["RATION_BASIC"])

    def test_work_settles_once(self):
        self.work_and_settle()
        self.svc.reconcile(); self.svc.reconcile()
        self.assertEqual(50, self.svc.balance("fa-player")["balance"])

    def test_idempotent_work(self):
        a = self.svc.queue_public_work("same", 2)
        b = self.svc.queue_public_work("same", 2)
        self.assertEqual(a, b)
        self.assertEqual(1, len(self.svc.list_actions()["items"]))

    def test_idempotency_conflict(self):
        self.svc.queue_public_work("same", 2)
        with self.assertRaises(ApiError) as cm:
            self.svc.queue_public_work("same", 3)
        self.assertEqual(409, cm.exception.status)

    def test_queue_limit(self):
        for i in range(10):
            self.svc.queue_public_work(f"q-{i}", 100)
        with self.assertRaises(ApiError) as cm:
            self.svc.queue_public_work("q-10", 100)
        self.assertEqual("ACTION_QUEUE_FULL", cm.exception.details["reason"])

    def test_insufficient_funds(self):
        with self.assertRaises(ApiError) as cm:
            self.svc.purchase("lst-ration-basic", 1, "buy-no-money")
        self.assertEqual("INSUFFICIENT_FUNDS", cm.exception.details["reason"])

    def test_ledger_zero_sum(self):
        self.work_and_settle()
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT transaction_id,SUM(amount) total FROM ledger_entries GROUP BY transaction_id").fetchall()
            self.assertTrue(rows)
            self.assertTrue(all(r["total"] == 0 for r in rows))

    def test_events_emitted(self):
        self.work_and_settle()
        types = {x["event_type"] for x in self.svc.events()["items"]}
        self.assertTrue({"ActionQueued", "ActionStarted", "PublicJobCompleted", "ActionCompleted"}.issubset(types))


if __name__ == "__main__":
    unittest.main()
