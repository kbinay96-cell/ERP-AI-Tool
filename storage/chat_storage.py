"""
storage/chat_storage.py

Persistent chat session storage - SQLite. Layer: Persistence.
ALL SQL for chat history lives here and ONLY here (mirrors Medical ERP V2's
own "SQL only inside Models" rule, applied to this tool itself).

Never call sqlite3 directly from ui/ files - always through this class.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_FILE_NAME = "chat_history.db"


class ChatStorage:
    """One connection per instance. Safe to create fresh instances per call
    (SQLite handles this fine for a single-user desktop app)."""

    def __init__(self, db_path: str = DB_FILE_NAME) -> None:
        self.db_path = db_path
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------ #
    # SESSION CRUD
    # ------------------------------------------------------------------ #
    def create_session(self, title: str = "New Chat") -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at, pinned) "
                "VALUES (?, ?, ?, ?, 0)",
                (session_id, title, now, now),
            )
            conn.commit()
        return session_id

    def list_sessions(self) -> list[dict]:
        """Pinned first, then most-recently-updated first."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY pinned DESC, updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def rename_session(self, session_id: str, new_title: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (new_title, datetime.now().isoformat(), session_id),
            )
            conn.commit()

    def set_pinned(self, session_id: str, pinned: bool) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET pinned = ? WHERE session_id = ?",
                (1 if pinned else 0, session_id),
            )
            conn.commit()

    def delete_session(self, session_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    def touch_session(self, session_id: str) -> None:
        """Updates the session's updated_at - call this after every new message,
        so the session list re-sorts to show most-recent chats on top."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (datetime.now().isoformat(), session_id),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # MESSAGE CRUD
    # ------------------------------------------------------------------ #
    def add_message(self, session_id: str, sender: str, content: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, sender, content, datetime.now().isoformat()),
            )
            conn.commit()
        self.touch_session(session_id)

    def get_messages(self, session_id: str) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY msg_id ASC",
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def auto_title_from_first_message(self, session_id: str, first_user_message: str) -> None:
        """Called once, right after the FIRST user message in a session - titles
        the session using a truncated version of that message, e.g. ChatGPT-style."""
        title = first_user_message.strip().replace("\n", " ")
        if len(title) > 50:
            title = title[:50].rstrip() + "..."
        self.rename_session(session_id, title or "New Chat")


__all__ = ["ChatStorage"]