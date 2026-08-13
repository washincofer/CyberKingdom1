import multiprocessing as mp
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


def worker_enqueue(db_path, key, out):
    try:
        GameService(Database(db_path)).queue_public_work(key, 100)
        out.put((key, "ok"))
    except ApiError as e:
        out.put((key, e.details.get("reason", e.code)))
    except Exception as e:
        out.put((key, "ERROR:" + repr(e)))


def worker_purchase(db_path, key, out):
    try:
        result = GameService(Database(db_path)).purchase("lst-ration-basic", 1, key)
        out.put((key, "ok", result["id"]))
    except ApiError as e:
        out.put((key, e.details.get("reason", e.code), None))
    except Exception as e:
        out.put((key, "ERROR:" + repr(e), None))


def worker_reconcile(db_path, out):
    try:
        out.put(("ok", GameService(Database(db_path)).reconcile()))
    except Exception as e:
        out.put(("ERROR", repr(e)))


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "concurrent.db")
        self.db = Database(self.path); self.db.initialize()
        self.svc = GameService(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, target, args_list):
        q = mp.Queue()
        ps = [mp.Process(target=target, args=(*args, q)) for args in args_list]
        for p in ps: p.start()
        for p in ps: p.join(20)
        self.assertTrue(all(not p.is_alive() for p in ps))
        return [q.get(timeout=2) for _ in ps]

    def test_concurrent_enqueue_stops_at_10(self):
        results = self._run(worker_enqueue, [(self.path, f"enq-{i}") for i in range(12)])
        oks = sum(r[1] == "ok" for r in results)
        self.assertEqual(10, oks, results)
        self.assertEqual(10, len([a for a in self.svc.list_actions()["items"] if a["status"] in ("QUEUED","RUNNING")]))

    def test_concurrent_last_item_has_one_winner(self):
        with self.db.transaction(immediate=True) as conn:
            conn.execute("UPDATE market_listings SET available_qty=1,status='ACTIVE' WHERE id='lst-ration-basic'")
            conn.execute("UPDATE financial_accounts SET balance=100 WHERE id='fa-player'")
        results = self._run(worker_purchase, [(self.path, "buy-a"), (self.path, "buy-b")])
        self.assertEqual(1, sum(r[1] == "ok" for r in results), results)
        with self.db.transaction() as conn:
            qty = conn.execute("SELECT available_qty FROM market_listings WHERE id='lst-ration-basic'").fetchone()[0]
            inv = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM inventory_items WHERE inventory_id='inv-player' AND item_code='RATION_BASIC'").fetchone()[0]
        self.assertEqual(0, qty)
        self.assertEqual(1, inv)

    def test_concurrent_same_idempotency_key_creates_one_purchase(self):
        with self.db.transaction(immediate=True) as conn:
            conn.execute("UPDATE financial_accounts SET balance=100 WHERE id='fa-player'")
        results = self._run(worker_purchase, [(self.path, "same-buy"), (self.path, "same-buy")])
        self.assertTrue(all(r[1] == "ok" for r in results), results)
        self.assertEqual(results[0][2], results[1][2])
        with self.db.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0])

    def test_two_reconcilers_settle_once(self):
        self.svc.queue_public_work("work", 1)
        time.sleep(1.05)
        results = self._run(worker_reconcile, [(self.path,), (self.path,)])
        self.assertTrue(all(r[0] == "ok" for r in results), results)
        self.assertEqual(50, self.svc.balance("fa-player")["balance"])
        with self.db.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM action_settlements").fetchone()[0])


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    unittest.main()
