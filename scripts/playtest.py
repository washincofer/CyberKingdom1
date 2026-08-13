import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from cyberkingdoms.api import DEFAULT_DB
from cyberkingdoms.db import Database
from cyberkingdoms.service import GameService

db = Database(DEFAULT_DB); db.reset(); svc = GameService(db)
report = {"journey": "VS-001", "steps": []}
def add(name, data): report["steps"].append({"step": name, "result": data})
add("initial", {"me": svc.me(), "balance": svc.balance("fa-player")})
add("public_work", svc.queue_public_work("playtest-work", 1))
time.sleep(1.05); add("reconcile", svc.reconcile())
add("balance_after_work", svc.balance("fa-player"))
add("purchase", svc.purchase("lst-ration-basic", 1, "playtest-buy"))
add("inventory_after_purchase", svc.inventory("inv-player"))
add("consume", svc.consume("RATION_BASIC", 1, "playtest-eat"))
add("final", {"me": svc.me(), "balance": svc.balance("fa-player"), "inventory": svc.inventory("inv-player")})
report["status"] = "PASS" if report["steps"][-1]["result"]["balance"]["balance"] == 30 else "FAIL"
out = ROOT / "playtest-report.json"; out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(report, indent=2, ensure_ascii=False))
print(f"\nReport: {out}")
