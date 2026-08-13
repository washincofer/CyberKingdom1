from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .db import Database
from .errors import ApiError

QUEUE_LIMIT = 10


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    dt = dt or utcnow()
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class GameService:
    def __init__(self, db: Database):
        self.db = db

    def health(self):
        return {"status": "ok", "service": "cyberkingdoms-sqlite-prototype", "database": "sqlite", "time": iso()}

    def _param(self, conn, key: str) -> int:
        row = conn.execute("SELECT value FROM demo_params WHERE key=?", (key,)).fetchone()
        return int(row["value"])

    def _event(self, conn, event_type: str, aggregate_id: str, payload: dict):
        conn.execute(
            "INSERT INTO outbox_events(event_id,event_type,event_version,aggregate_id,occurred_at,payload_json) VALUES (?,?,?,?,?,?)",
            (new_id("evt"), event_type, 1, aggregate_id, iso(), Database.json(payload)),
        )

    def _transfer(self, conn, reference_type: str, reference_id: str, entries: list[tuple[str, int]]):
        if sum(amount for _, amount in entries) != 0:
            raise RuntimeError("Ledger entries must sum to zero")
        txn_id = new_id("txn")
        conn.execute(
            "INSERT INTO ledger_transactions(id,reference_type,reference_id,currency,posted_at) VALUES (?,?,?,?,?)",
            (txn_id, reference_type, reference_id, "Cz", iso()),
        )
        for account_id, amount in entries:
            conn.execute(
                "INSERT INTO ledger_entries(transaction_id,account_id,amount) VALUES (?,?,?)",
                (txn_id, account_id, amount),
            )
        return txn_id

    def _idempotent_get(self, conn, key: str, operation: str, body: dict):
        if not key:
            raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key header is required.")
        body_hash = hashlib.sha256(Database.json(body).encode()).hexdigest()
        row = conn.execute("SELECT * FROM idempotency_records WHERE idempotency_key=?", (key,)).fetchone()
        if row:
            if row["operation"] != operation or row["body_hash"] != body_hash:
                raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "Idempotency key reused with different request.")
            return body_hash, json.loads(row["response_json"])
        return body_hash, None

    def _idempotent_put(self, conn, key: str, operation: str, body_hash: str, response: dict):
        conn.execute(
            "INSERT INTO idempotency_records(idempotency_key,operation,body_hash,response_json,created_at) VALUES (?,?,?,?,?)",
            (key, operation, body_hash, Database.json(response), iso()),
        )

    def _reindex(self, conn, citizen_id: str = "cit-player"):
        rows = conn.execute(
            "SELECT id FROM actions WHERE citizen_id=? AND status IN ('QUEUED','RUNNING') ORDER BY starts_at,id",
            (citizen_id,),
        ).fetchall()
        # Move rows to a safe positive range first to avoid unique-index collisions.
        # The schema intentionally forbids position < 1.
        for idx, row in enumerate(rows, 1):
            conn.execute("UPDATE actions SET position=? WHERE id=?", (1000 + idx, row["id"]))
        for idx, row in enumerate(rows, 1):
            conn.execute("UPDATE actions SET position=? WHERE id=?", (idx, row["id"]))

    def _settle_action(self, conn, action, now: datetime):
        existing = conn.execute("SELECT 1 FROM action_settlements WHERE action_id=?", (action["id"],)).fetchone()
        if existing:
            conn.execute("UPDATE actions SET status='COMPLETED', completed_at=COALESCE(completed_at,?) WHERE id=?", (iso(now), action["id"]))
            return False

        result = {}
        if action["type"] == "PUBLIC_WORK":
            reward = self._param(conn, "public_work_reward_cz")
            energy_cost = self._param(conn, "public_work_energy_cost")
            conn.execute("UPDATE financial_accounts SET balance=balance+? WHERE id='fa-player'", (reward,))
            conn.execute("UPDATE financial_accounts SET balance=balance-? WHERE id='fa-treasury'", (reward,))
            conn.execute("UPDATE citizens SET energy=MAX(0,energy-?) WHERE id=?", (energy_cost, action["citizen_id"]))
            self._transfer(conn, "PUBLIC_WORK_REWARD", action["id"], [("fa-treasury", -reward), ("fa-player", reward)])
            result = {"reward_cz": reward, "energy_cost": energy_cost}
            self._event(conn, "PublicJobCompleted", action["id"], {"action_id": action["id"], "reward_cz": reward})

        conn.execute(
            "INSERT INTO action_settlements(action_id,settled_at,result_json) VALUES (?,?,?)",
            (action["id"], iso(now), Database.json(result)),
        )
        conn.execute("UPDATE actions SET status='COMPLETED', completed_at=? WHERE id=?", (iso(now), action["id"]))
        self._event(conn, "ActionCompleted", action["id"], {"action_id": action["id"], "type": action["type"]})
        return True

    def _reconcile_in_tx(self, conn):
        now = utcnow()
        started = completed = 0
        rows = conn.execute(
            "SELECT * FROM actions WHERE status IN ('QUEUED','RUNNING') ORDER BY position,id"
        ).fetchall()
        for action in rows:
            starts_at = parse_iso(action["starts_at"])
            due_at = parse_iso(action["due_at"])
            status = action["status"]
            if status == "QUEUED" and starts_at <= now:
                conn.execute("UPDATE actions SET status='RUNNING', started_at=? WHERE id=?", (action["starts_at"], action["id"]))
                self._event(conn, "ActionStarted", action["id"], {"action_id": action["id"], "type": action["type"]})
                started += 1
                status = "RUNNING"
            if status in ("QUEUED", "RUNNING") and due_at <= now:
                if status == "QUEUED":
                    conn.execute("UPDATE actions SET status='RUNNING', started_at=? WHERE id=?", (action["starts_at"], action["id"]))
                    self._event(conn, "ActionStarted", action["id"], {"action_id": action["id"], "type": action["type"]})
                    started += 1
                refreshed = conn.execute("SELECT * FROM actions WHERE id=?", (action["id"],)).fetchone()
                if self._settle_action(conn, refreshed, now):
                    completed += 1
        self._reindex(conn)
        return {"started": started, "completed": completed}

    def reconcile(self):
        with self.db.transaction(immediate=True) as conn:
            return self._reconcile_in_tx(conn)

    def me(self):
        self.reconcile()
        with self.db.transaction() as conn:
            account = dict(conn.execute("SELECT * FROM accounts WHERE id='acc-player'").fetchone())
            citizen = dict(conn.execute("SELECT * FROM citizens WHERE id='cit-player'").fetchone())
            citizen["vitals"] = {"hunger": citizen.pop("hunger"), "energy": citizen.pop("energy")}
            return {"account": account, "citizen": citizen, "financial_account_id": "fa-player", "inventory_id": "inv-player"}

    def list_actions(self):
        self.reconcile()
        with self.db.transaction() as conn:
            items = [dict(r) for r in conn.execute("SELECT * FROM actions ORDER BY CASE WHEN status IN ('QUEUED','RUNNING') THEN 0 ELSE 1 END, position, created_at").fetchall()]
            return {"items": items, "limit": QUEUE_LIMIT}

    def get_action(self, action_id: str):
        self.reconcile()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise ApiError(404, "RESOURCE_NOT_FOUND", "Action not found.")
            return dict(row)

    def queue_public_work(self, idempotency_key: str, duration_seconds: int = 2):
        if duration_seconds < 1 or duration_seconds > 86400:
            raise ApiError(422, "RULE_VIOLATION", "Invalid duration.", {"reason": "DURATION_OUT_OF_RANGE"})
        body = {"type": "PUBLIC_WORK", "duration_seconds": duration_seconds}
        with self.db.transaction(immediate=True) as conn:
            self._reconcile_in_tx(conn)
            body_hash, cached = self._idempotent_get(conn, idempotency_key, "queue_public_work", body)
            if cached is not None:
                return cached
            pending = conn.execute("SELECT * FROM actions WHERE citizen_id='cit-player' AND status IN ('QUEUED','RUNNING') ORDER BY due_at DESC LIMIT 1").fetchall()
            count = conn.execute("SELECT COUNT(*) AS n FROM actions WHERE citizen_id='cit-player' AND status IN ('QUEUED','RUNNING')").fetchone()["n"]
            if count >= QUEUE_LIMIT:
                raise ApiError(422, "RULE_VIOLATION", "Action queue limit reached.", {"reason": "ACTION_QUEUE_FULL", "limit": QUEUE_LIMIT})
            now = utcnow()
            start = now if not pending else max(now, parse_iso(pending[0]["due_at"]))
            due = start + timedelta(seconds=duration_seconds)
            action_id = new_id("act")
            position = count + 1
            status = "RUNNING" if start <= now else "QUEUED"
            started_at = iso(start) if status == "RUNNING" else None
            action = {
                "id": action_id, "citizen_id": "cit-player", "type": "PUBLIC_WORK", "status": status,
                "position": position, "starts_at": iso(start), "due_at": iso(due), "created_at": iso(now),
                "started_at": started_at, "completed_at": None,
            }
            conn.execute(
                "INSERT INTO actions(id,citizen_id,type,status,position,starts_at,due_at,created_at,started_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                tuple(action[k] for k in ("id","citizen_id","type","status","position","starts_at","due_at","created_at","started_at","completed_at")),
            )
            self._event(conn, "ActionQueued", action_id, {"action_id": action_id, "type": "PUBLIC_WORK"})
            if status == "RUNNING":
                self._event(conn, "ActionStarted", action_id, {"action_id": action_id, "type": "PUBLIC_WORK"})
            self._event(conn, "PublicJobStarted", action_id, {"action_id": action_id})
            response = {"public_job_id": "job-" + action_id[4:], "action": action}
            self._idempotent_put(conn, idempotency_key, "queue_public_work", body_hash, response)
            return response

    def cancel_action(self, action_id: str):
        with self.db.transaction(immediate=True) as conn:
            self._reconcile_in_tx(conn)
            row = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise ApiError(404, "RESOURCE_NOT_FOUND", "Action not found.")
            if row["status"] != "QUEUED":
                raise ApiError(409, "STATE_CONFLICT", "Only queued actions can be canceled.", {"reason": "ACTION_ALREADY_STARTED"})
            conn.execute("UPDATE actions SET status='INTERRUPTED', completed_at=? WHERE id=?", (iso(), action_id))
            self._event(conn, "ActionInterrupted", action_id, {"action_id": action_id, "reason": "CANCELED_BEFORE_START"})
            self._reindex(conn)
            return dict(conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())

    def balance(self, account_id: str):
        if account_id != "fa-player":
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Financial account not found.")
        self.reconcile()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT balance,currency FROM financial_accounts WHERE id=?", (account_id,)).fetchone()
            return {"account_id": account_id, "currency": row["currency"], "balance": row["balance"], "available": row["balance"]}

    def transactions(self, account_id: str):
        if account_id != "fa-player":
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Financial account not found.")
        with self.db.transaction() as conn:
            txns = []
            for txn in conn.execute("SELECT * FROM ledger_transactions ORDER BY posted_at,id").fetchall():
                entries = [dict(r) for r in conn.execute("SELECT account_id AS account, amount FROM ledger_entries WHERE transaction_id=? ORDER BY id", (txn["id"],)).fetchall()]
                item = dict(txn); item["entries"] = entries; txns.append(item)
            return {"items": txns}

    def inventory(self, inventory_id: str):
        if inventory_id != "inv-player":
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Inventory not found.")
        with self.db.transaction() as conn:
            items = {r["item_code"]: r["quantity"] for r in conn.execute("SELECT item_code,quantity FROM inventory_items WHERE inventory_id=?", (inventory_id,)).fetchall()}
            return {"id": inventory_id, "items": items}

    def listings(self, city_id: str):
        with self.db.transaction() as conn:
            exists = conn.execute("SELECT 1 FROM citizens WHERE id='cit-player' AND city_id=?", (city_id,)).fetchone()
            if not exists:
                raise ApiError(404, "RESOURCE_NOT_FOUND", "Market not found.")
            return {"items": [dict(r) for r in conn.execute("SELECT * FROM market_listings WHERE city_id=? AND status='ACTIVE' ORDER BY id", (city_id,)).fetchall()]}

    def purchase(self, listing_id: str, quantity: int, idempotency_key: str):
        if quantity < 1:
            raise ApiError(400, "VALIDATION_FAILED", "Quantity must be >= 1.")
        body = {"listing_id": listing_id, "quantity": quantity}
        with self.db.transaction(immediate=True) as conn:
            body_hash, cached = self._idempotent_get(conn, idempotency_key, "purchase", body)
            if cached is not None:
                return cached
            listing = conn.execute("SELECT * FROM market_listings WHERE id=? AND status='ACTIVE'", (listing_id,)).fetchone()
            if not listing:
                raise ApiError(404, "RESOURCE_NOT_FOUND", "Listing not found.")
            if listing["available_qty"] < quantity:
                raise ApiError(409, "STATE_CONFLICT", "Not enough quantity.", {"reason": "LISTING_STOCK_CHANGED"})
            total = listing["price_cz"] * quantity
            balance = conn.execute("SELECT balance FROM financial_accounts WHERE id='fa-player'").fetchone()["balance"]
            if balance < total:
                raise ApiError(422, "RULE_VIOLATION", "Insufficient Cz.", {"reason": "INSUFFICIENT_FUNDS"})
            conn.execute("UPDATE financial_accounts SET balance=balance-? WHERE id='fa-player'", (total,))
            conn.execute("UPDATE financial_accounts SET balance=balance+? WHERE id='fa-market-sink'", (total,))
            self._transfer(conn, "MARKET_PURCHASE", listing_id, [("fa-player", -total), ("fa-market-sink", total)])
            new_qty = listing["available_qty"] - quantity
            conn.execute("UPDATE market_listings SET available_qty=?, status=? WHERE id=?", (new_qty, "CLOSED" if new_qty == 0 else "ACTIVE", listing_id))
            conn.execute(
                "INSERT INTO inventory_items(inventory_id,item_code,quantity) VALUES ('inv-player',?,?) ON CONFLICT(inventory_id,item_code) DO UPDATE SET quantity=quantity+excluded.quantity",
                (listing["item_code"], quantity),
            )
            purchase_id = new_id("pur")
            response = {"id": purchase_id, "mode": "DIRECT", "status": "COMPLETED", "listing_id": listing_id, "quantity": quantity, "total_cz": total, "item_code": listing["item_code"]}
            conn.execute("INSERT INTO purchases(id,listing_id,quantity,total_cz,item_code,status,created_at) VALUES (?,?,?,?,?,?,?)", (purchase_id, listing_id, quantity, total, listing["item_code"], "COMPLETED", iso()))
            self._event(conn, "PurchaseCompleted", purchase_id, response)
            self._idempotent_put(conn, idempotency_key, "purchase", body_hash, response)
            return response

    def consume(self, item_code: str, quantity: int, idempotency_key: str):
        if quantity != 1:
            raise ApiError(422, "RULE_VIOLATION", "Prototype supports consuming one item at a time.", {"reason": "UNSUPPORTED_CONSUME_QUANTITY"})
        body = {"item_code": item_code, "quantity": quantity}
        with self.db.transaction(immediate=True) as conn:
            body_hash, cached = self._idempotent_get(conn, idempotency_key, "consume", body)
            if cached is not None:
                return cached
            row = conn.execute("SELECT quantity FROM inventory_items WHERE inventory_id='inv-player' AND item_code=?", (item_code,)).fetchone()
            if not row or row["quantity"] < 1:
                raise ApiError(422, "RULE_VIOLATION", "Item unavailable.", {"reason": "ITEM_NOT_AVAILABLE"})
            if item_code != "RATION_BASIC":
                raise ApiError(422, "RULE_VIOLATION", "Item is not consumable in this slice.", {"reason": "ITEM_NOT_CONSUMABLE"})
            conn.execute("UPDATE inventory_items SET quantity=quantity-1 WHERE inventory_id='inv-player' AND item_code=?", (item_code,))
            gain = self._param(conn, "ration_hunger_gain")
            conn.execute("UPDATE citizens SET hunger=MIN(100,hunger+?) WHERE id='cit-player'", (gain,))
            vitals = dict(conn.execute("SELECT hunger,energy FROM citizens WHERE id='cit-player'").fetchone())
            response = {"item_code": item_code, "quantity": 1, "vitals": vitals}
            self._event(conn, "ItemConsumed", "cit-player", response)
            self._idempotent_put(conn, idempotency_key, "consume", body_hash, response)
            return response

    def events(self):
        with self.db.transaction() as conn:
            items = []
            for row in conn.execute("SELECT * FROM outbox_events ORDER BY occurred_at,event_id").fetchall():
                item = dict(row); item["payload"] = json.loads(item.pop("payload_json")); items.append(item)
            return {"items": items}
