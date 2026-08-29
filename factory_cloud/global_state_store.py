from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS global_dispatch_batches (
    batch_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    created_at REAL NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','PARTIAL','DONE','BLOCKED','ERROR'))
);
CREATE TABLE IF NOT EXISTS global_dispatch_items (
    batch_id TEXT NOT NULL REFERENCES global_dispatch_batches(batch_id) ON DELETE CASCADE,
    factory_id TEXT NOT NULL,
    route TEXT NOT NULL,
    worker_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','WAIT','BLOCKED','DONE','ERROR')),
    blocker TEXT,
    result_json TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY(batch_id, factory_id)
);
CREATE INDEX IF NOT EXISTS idx_global_dispatch_items_state ON global_dispatch_items(state, updated_at);
"""

class GlobalStateStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db: db.executescript(SCHEMA)
    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30); db.row_factory = sqlite3.Row; return db
    def create_batch(self, scope: str, routes: Iterable[dict[str, Any]]) -> str:
        batch_id = str(uuid.uuid4()); now = time.time(); routes = list(routes)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO global_dispatch_batches(batch_id,scope,created_at,state) VALUES(?,?,?,?)",(batch_id,scope,now,"QUEUED"))
            for route in routes:
                db.execute("INSERT INTO global_dispatch_items(batch_id,factory_id,route,worker_key,state,blocker,result_json,updated_at) VALUES(?,?,?,?,?,?,?,?)",(batch_id,str(route["factory_id"]),str(route["route"]),str(route["worker_key"]),"QUEUED",None,None,now))
            db.commit()
        return batch_id
    def update_item(self,batch_id:str,factory_id:str,state:str,*,blocker:str|None=None,result:dict[str,Any]|None=None)->None:
        if state not in {"QUEUED","RUNNING","WAIT","BLOCKED","DONE","ERROR"}: raise ValueError(f"invalid item state: {state}")
        encoded=None if result is None else json.dumps(result,sort_keys=True,ensure_ascii=False)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cur=db.execute("UPDATE global_dispatch_items SET state=?,blocker=?,result_json=?,updated_at=? WHERE batch_id=? AND factory_id=?",(state,blocker,encoded,time.time(),batch_id,factory_id))
            if cur.rowcount!=1: db.rollback(); raise KeyError((batch_id,factory_id))
            self._recompute_batch(db,batch_id); db.commit()
    def _recompute_batch(self,db:sqlite3.Connection,batch_id:str)->None:
        states=[row[0] for row in db.execute("SELECT state FROM global_dispatch_items WHERE batch_id=?",(batch_id,))]
        if not states or all(s=="DONE" for s in states): batch_state="DONE"
        elif any(s=="ERROR" for s in states): batch_state="ERROR"
        elif any(s in {"RUNNING","QUEUED"} for s in states): batch_state="RUNNING"
        elif all(s in {"WAIT","BLOCKED"} for s in states): batch_state="BLOCKED"
        else: batch_state="PARTIAL"
        db.execute("UPDATE global_dispatch_batches SET state=? WHERE batch_id=?",(batch_state,batch_id))
    def batch(self,batch_id:str)->dict[str,Any]:
        with self._connect() as db:
            batch=db.execute("SELECT * FROM global_dispatch_batches WHERE batch_id=?",(batch_id,)).fetchone()
            if batch is None: raise KeyError(batch_id)
            items=db.execute("SELECT * FROM global_dispatch_items WHERE batch_id=? ORDER BY factory_id",(batch_id,)).fetchall()
        return {"batch_id":batch["batch_id"],"scope":batch["scope"],"created_at":batch["created_at"],"state":batch["state"],"items":[{"factory_id":r["factory_id"],"route":r["route"],"worker_key":r["worker_key"],"state":r["state"],"blocker":r["blocker"],"result":json.loads(r["result_json"]) if r["result_json"] else None,"updated_at":r["updated_at"]} for r in items]}
