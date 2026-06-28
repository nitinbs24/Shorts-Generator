"""
shared/db.py — SQLite database layer for the YouTube Shorts Automation pipeline.

Tables:
    uploads      — every upload attempt (auto + Veo)
    veo_queue    — daily Veo scripts and prompts for the manual workflow
    topics_used  — deduplication tracking (30-day rolling window)
    blacklist    — operator-managed topic exclusions per channel

Call init_db() once on startup to create all tables if they don't exist.
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from shared.config import DB_PATH

logger = logging.getLogger(__name__)


# ── Connection ────────────────────────────────────────────────────────────────

def _get_connection() -> sqlite3.Connection:
    """Open and return a SQLite connection with row_factory set."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Schema initialisation ─────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they do not already exist."""
    with _get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS uploads (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                channel         TEXT    NOT NULL,
                mode            TEXT    NOT NULL,           -- 'auto' or 'veo'
                title           TEXT,
                topic           TEXT,
                youtube_id      TEXT,
                status          TEXT    DEFAULT 'pending',  -- pending | success | failed
                error_message   TEXT,
                created_at      TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS veo_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel     TEXT    NOT NULL,
                topic       TEXT,
                script      TEXT,
                veo_prompt  TEXT,
                status      TEXT    DEFAULT 'pending',      -- pending | downloaded | uploaded
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS topics_used (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel     TEXT    NOT NULL,
                topic       TEXT    NOT NULL,
                used_at     TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel     TEXT    NOT NULL,
                topic       TEXT    NOT NULL,
                added_at    TEXT    DEFAULT (datetime('now'))
            );
        """)
    logger.info(f"Database initialised at: {DB_PATH}")


# ── Uploads ───────────────────────────────────────────────────────────────────

def log_upload(
    channel: str,
    mode: str,
    title: str,
    topic: str,
    youtube_id: Optional[str] = None,
    status: str = "pending",
    error_message: Optional[str] = None,
) -> int:
    """Insert a new upload record. Returns the row ID."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO uploads
               (channel, mode, title, topic, youtube_id, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (channel, mode, title, topic, youtube_id, status, error_message),
        )
        logger.debug(f"Upload logged: id={cursor.lastrowid} channel={channel} status={status}")
        return cursor.lastrowid


def update_upload_status(
    upload_id: int,
    status: str,
    youtube_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update the status (and optionally youtube_id / error_message) of an upload record."""
    with _get_connection() as conn:
        conn.execute(
            """UPDATE uploads
               SET status=?, youtube_id=?, error_message=?
               WHERE id=?""",
            (status, youtube_id, error_message, upload_id),
        )
    logger.debug(f"Upload {upload_id} updated to status={status}")


def get_upload_history(
    channel: Optional[str] = None,
    days: int = 30,
    mode: Optional[str] = None,
) -> list[dict]:
    """Return upload records for the given channel within the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = "SELECT * FROM uploads WHERE created_at > ?"
    params: list = [cutoff]

    if channel:
        query += " AND channel=?"
        params.append(channel.upper())
    if mode:
        query += " AND mode=?"
        params.append(mode)

    query += " ORDER BY created_at DESC"

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_today_uploads(channel: Optional[str] = None) -> list[dict]:
    """Return all upload records for today (UTC date)."""
    today = datetime.now(timezone.utc).date().isoformat()
    query = "SELECT * FROM uploads WHERE DATE(created_at)=?"
    params: list = [today]

    if channel:
        query += " AND channel=?"
        params.append(channel.upper())

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Veo queue ─────────────────────────────────────────────────────────────────

def store_veo_entry(channel: str, topic: str, script: str, veo_prompt: str) -> int:
    """Insert a new Veo queue entry. Returns the row ID."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO veo_queue (channel, topic, script, veo_prompt)
               VALUES (?, ?, ?, ?)""",
            (channel.upper(), topic, script, veo_prompt),
        )
        logger.debug(f"Veo entry stored: id={cursor.lastrowid} channel={channel} topic={topic}")
        return cursor.lastrowid


def get_pending_veo(channel: Optional[str] = None) -> list[dict]:
    """Return all pending Veo queue entries, optionally filtered by channel."""
    query = "SELECT * FROM veo_queue WHERE status='pending'"
    params: list = []

    if channel:
        query += " AND channel=?"
        params.append(channel.upper())

    query += " ORDER BY created_at DESC"

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_veo_status(veo_id: int, status: str) -> None:
    """Update the status of a Veo queue entry (pending → downloaded → uploaded)."""
    with _get_connection() as conn:
        conn.execute("UPDATE veo_queue SET status=? WHERE id=?", (status, veo_id))
    logger.debug(f"Veo entry {veo_id} updated to status={status}")


# ── Topic deduplication ───────────────────────────────────────────────────────

def is_topic_used(channel: str, topic: str, days: int = 30) -> bool:
    """Return True if the topic has been used for this channel within the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _get_connection() as conn:
        row = conn.execute(
            """SELECT 1 FROM topics_used
               WHERE channel=? AND topic=? AND used_at > ?""",
            (channel.upper(), topic.lower().strip(), cutoff),
        ).fetchone()
    return row is not None


def mark_topic_used(channel: str, topic: str) -> None:
    """Record a topic as used for the given channel."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO topics_used (channel, topic) VALUES (?, ?)",
            (channel.upper(), topic.lower().strip()),
        )
    logger.debug(f"Topic marked as used: channel={channel} topic={topic}")


# ── Blacklist ─────────────────────────────────────────────────────────────────

def get_blacklist(channel: str) -> list[dict]:
    """Return all blacklisted topics for a channel."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM blacklist WHERE channel=? ORDER BY added_at DESC",
            (channel.upper(),),
        ).fetchall()
    return [dict(r) for r in rows]


def is_blacklisted(channel: str, topic: str) -> bool:
    """Return True if the topic is on the blacklist for this channel."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM blacklist WHERE channel=? AND topic=?",
            (channel.upper(), topic.lower().strip()),
        ).fetchone()
    return row is not None


def add_to_blacklist(channel: str, topic: str) -> None:
    """Add a topic to the blacklist for the given channel."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO blacklist (channel, topic) VALUES (?, ?)",
            (channel.upper(), topic.lower().strip()),
        )
    logger.info(f"Blacklisted topic: channel={channel} topic={topic}")


def remove_from_blacklist(blacklist_id: int) -> None:
    """Remove a blacklist entry by its row ID."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM blacklist WHERE id=?", (blacklist_id,))
    logger.info(f"Removed blacklist entry: id={blacklist_id}")
