"""Transactional SQLite snapshot, shared safely across requests and workers."""
import json
import sqlite3
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path
from .dataset import validate

class Store:
    def __init__(self, path, initial):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS shares (id TEXT PRIMARY KEY, owner TEXT NOT NULL, recipients TEXT NOT NULL, card TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS coins (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, amount INTEGER NOT NULL, event_id TEXT, request_id TEXT, item_id TEXT, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(owner,event_id), UNIQUE(owner,request_id))")
            db.execute("CREATE TABLE IF NOT EXISTS wallet_meta (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO wallet_meta VALUES (1,1)")
            db.execute("INSERT OR IGNORE INTO state VALUES (1, 1, ?)", (json.dumps(validate(initial)),))

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def read(self):
        with closing(self.connect()) as db, db:
            version, payload = db.execute("SELECT revision,payload FROM state WHERE id=1").fetchone()
            return json.loads(payload), version

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            revision, payload = db.execute("SELECT revision,payload FROM state WHERE id=1").fetchone()
            state = {"data":json.loads(payload), "revision":revision, "changed":False,"db":db}
            yield state
            if state["changed"]:
                db.execute("UPDATE state SET revision=?,payload=? WHERE id=1", (revision+1,json.dumps(state["data"])))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
