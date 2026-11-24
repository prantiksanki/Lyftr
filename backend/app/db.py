import json
import logging
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL,
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  metadata    TEXT,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS sessions (
  session_id    TEXT PRIMARY KEY,
  system_prompt TEXT,
  created_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path if self._writable(path) else self._fallback(path)

    @staticmethod
    def _writable(path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            c = sqlite3.connect(path, timeout=15)
            c.execute("CREATE TABLE IF NOT EXISTS _probe(x)")
            c.execute("DROP TABLE _probe")
            c.commit()
            c.close()
            return True
        except Exception:
            return False

    @staticmethod
    def _fallback(path: str) -> str:
        fb = os.path.join(tempfile.gettempdir(), "app.db")
        logging.getLogger("db").warning(
            "Cannot write database at %s; falling back to %s (history will NOT persist). "
            "Check DATABASE_URL and the disk mount permissions.", path, fb
        )
        return fb

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def init(self) -> None:
        with self.conn() as c:
            c.executescript(SCHEMA)

    def ping(self) -> bool:
        try:
            with self.conn() as c:
                c.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def session_exists(self, session_id: str) -> bool:
        with self.conn() as c:
            r = c.execute("SELECT 1 FROM messages WHERE session_id=? LIMIT 1", (session_id,)).fetchone()
        return r is not None

    def get_system_prompt(self, session_id: str):
        with self.conn() as c:
            r = c.execute("SELECT system_prompt FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return r["system_prompt"] if r else None

    def get_history(self, session_id: str):
        with self.conn() as c:
            rows = c.execute(
                "SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else None,
            }
            for r in rows
        ]

    def save_exchange(self, session_id, system_prompt, user_msg, reply, metadata) -> None:
        """Persist user + assistant messages atomically (only called on success)."""
        now = _now()
        with self.conn() as c:
            c.execute(
                "INSERT INTO sessions(session_id, system_prompt, created_at) VALUES(?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET system_prompt=excluded.system_prompt",
                (session_id, system_prompt, now),
            )
            c.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES(?,?,?,?,?)",
                (session_id, "user", user_msg, None, now),
            )
            c.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES(?,?,?,?,?)",
                (session_id, "assistant", reply, json.dumps(metadata), _now()),
            )
