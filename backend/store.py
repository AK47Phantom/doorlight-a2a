"""Small SQLite store for reload-safe Doorlight sessions, artifacts, and audit events."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from threading import Lock

class DoorlightStore:
    def __init__(self, path: str = "backend/doorlight.db") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = Lock()
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, case_id TEXT, session_id TEXT, data TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts (id INTEGER PRIMARY KEY, run_id TEXT, agent_id TEXT, data TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, run_id TEXT, agent_id TEXT, tool_name TEXT, purpose TEXT, decision TEXT, summary TEXT, created_at TEXT NOT NULL);
            """)
    def save_run(self, run: dict) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?)", (run["id"], run["caseId"], run["sessionId"], json.dumps(run), run["createdAt"]))
    def get_run(self, run_id: str) -> dict | None:
        row = self.db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row["data"]) if row else None
    def list_runs(self) -> list[dict]:
        return [json.loads(r["data"]) for r in self.db.execute("SELECT data FROM runs ORDER BY created_at DESC LIMIT 100")]
    def save_artifact(self, run_id: str, agent_id: str, artifact: dict, now: str) -> None:
        with self.lock, self.db: self.db.execute("INSERT INTO artifacts(run_id,agent_id,data,created_at) VALUES(?,?,?,?)", (run_id,agent_id,json.dumps(artifact),now))
    def has_artifact(self, run_id: str, agent_id: str) -> bool:
        row = self.db.execute("SELECT 1 FROM artifacts WHERE run_id=? AND agent_id=? LIMIT 1", (run_id, agent_id)).fetchone()
        return row is not None
    def audit(self, run_id: str, agent: str, tool: str, purpose: str, decision: str, summary: str, now: str) -> None:
        with self.lock, self.db: self.db.execute("INSERT INTO audit_log(run_id,agent_id,tool_name,purpose,decision,summary,created_at) VALUES(?,?,?,?,?,?,?)", (run_id,agent,tool,purpose,decision,summary,now))
