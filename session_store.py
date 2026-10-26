"""Bounded per-app conversations, separate from the study journal."""
import json
import sqlite3
import time

from storage import data_dir


def _connect():
    conn = sqlite3.connect(data_dir() / "conversations.db")
    conn.execute("CREATE TABLE IF NOT EXISTS conversations (app TEXT PRIMARY KEY, updated REAL NOT NULL, messages TEXT NOT NULL)")
    return conn


def load(app):
    with _connect() as conn:
        row = conn.execute("SELECT messages FROM conversations WHERE app=?", (app,)).fetchone()
    return json.loads(row[0]) if row else []


def save(app, messages):
    rows, remaining = [], 24000
    for message in reversed(messages[-20:]):
        if len(message.content) > remaining:
            break
        rows.insert(0, {"role": message.role, "content": message.content})
        remaining -= len(message.content)
    while rows and rows[0]["role"] != "user":
        rows.pop(0)
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO conversations VALUES (?, ?, ?)", (app, time.time(), json.dumps(rows)))
    return rows


def clear():
    with _connect() as conn:
        conn.execute("DELETE FROM conversations")


def recent():
    with _connect() as conn:
        return [(app, json.loads(messages)) for app, messages in conn.execute("SELECT app,messages FROM conversations ORDER BY updated DESC LIMIT 30")]
