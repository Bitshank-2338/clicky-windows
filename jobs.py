"""Local background answers and recurring routines; never runs unattended desktop actions."""
import json
import sqlite3
import time
import uuid

from storage import data_dir, atomic_write


class JobStore:
    def _connect(self):
        conn = sqlite3.connect(data_dir() / "jobs.db")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, title TEXT, prompt TEXT, state TEXT, result TEXT,
            error TEXT, next_run REAL, interval INTEGER, updated REAL)""")
        return conn

    def recover(self):
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET state='interrupted',error='Clicky closed before this job finished' WHERE state='running'")

    def add(self, title, prompt, interval=0, next_run=None):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise ValueError("A job needs a prompt of 1–12000 characters")
        if type(interval) is not int or interval < 0 or (interval and interval < 60):
            raise ValueError("Routines must be at least one minute apart")
        title = title.strip()[:120] or prompt[:80]
        ident, now = uuid.uuid4().hex, time.time()
        with self._connect() as conn:
            conn.execute("INSERT INTO jobs VALUES (?,?,?,'queued','','',?,?,?)", (ident, title, prompt.strip(), now if next_run is None else next_run, interval, now))
        return ident

    def list(self):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY updated DESC LIMIT 100")]

    def claim(self, now=None):
        now = time.time() if now is None else now
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM jobs WHERE state IN ('queued','completed') AND next_run IS NOT NULL AND next_run<=? ORDER BY next_run LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE jobs SET state='running',error='',updated=? WHERE id=?", (now, row['id']))
            return dict(row)

    def finish(self, ident, result='', error=''):
        now = time.time()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
            if not row or row['state'] != 'running':
                return
            next_run = now + row['interval'] if row['interval'] and not error else None
            if not error:
                path = data_dir() / "workspaces" / ident / "answer.md"
                atomic_write(path, ("# " + row['title'] + "\n\n" + result).encode('utf-8'))
            conn.execute("UPDATE jobs SET state=?,result=?,error=?,next_run=?,updated=? WHERE id=?", ('failed' if error else 'completed', result, error, next_run, now, ident))

    def action(self, ident, action):
        with self._connect() as conn:
            if action == 'delete':
                conn.execute("DELETE FROM jobs WHERE id=? AND state!='running'", (ident,))
            elif action in {'pause','retry'}:
                conn.execute("UPDATE jobs SET state=?,next_run=?,updated=? WHERE id=?", ('paused' if action == 'pause' else 'queued', None if action == 'pause' else time.time(), time.time(), ident))
            else:
                raise ValueError("Unknown job action")
