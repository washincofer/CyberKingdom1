from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .api import DEFAULT_DB, run
from .db import Database
from .service import GameService


def main():
    parser = argparse.ArgumentParser(description="CyberKingdoms SQLite Prototype")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_server = sub.add_parser("serve")
    p_server.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p_server.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    p_reset = sub.add_parser("reset")
    p_reset.add_argument("--db", default=os.environ.get("CYBERKINGDOMS_DB", str(DEFAULT_DB)))
    p_worker = sub.add_parser("reconcile")
    p_worker.add_argument("--db", default=os.environ.get("CYBERKINGDOMS_DB", str(DEFAULT_DB)))
    args = parser.parse_args()

    if args.cmd == "serve":
        return run(args.host, args.port)
    db = Database(args.db)
    if args.cmd == "reset":
        db.reset(); print(f"reset: {db.path}")
    elif args.cmd == "reconcile":
        db.initialize(); print(json.dumps(GameService(db).reconcile(), indent=2))


if __name__ == "__main__":
    main()
