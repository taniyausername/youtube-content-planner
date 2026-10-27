import json
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta, timezone


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                video_id TEXT NOT NULL, observed_at TEXT NOT NULL, views INTEGER,
                PRIMARY KEY (video_id, observed_at));
            ''')

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, result: dict, videos: list):
        with self.connect() as conn:
            conn.execute('INSERT INTO runs VALUES (?, ?, ?)',
                         (result['id'], result['created_at'], json.dumps(result)))
            for v in videos:
                if not v.synthetic:
                    conn.execute('INSERT OR IGNORE INTO observations VALUES (?, ?, ?)',
                                 (v.id, v.observed_at.isoformat(), v.views))
            # Purge records older than 30 days on use; see README for idle-server cleanup.
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            conn.execute('DELETE FROM observations WHERE observed_at < ?', (cutoff,))
            conn.execute('DELETE FROM runs WHERE created_at < ?', (cutoff,))

    def history(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with self.connect() as conn:
            conn.execute('DELETE FROM runs WHERE created_at < ?', (cutoff,))
            conn.execute('DELETE FROM observations WHERE observed_at < ?', (cutoff,))
            rows = conn.execute('SELECT payload FROM runs ORDER BY created_at DESC LIMIT 50').fetchall()
        return [{'id': r['id'], 'created_at': r['created_at'], 'request': r['request'],
                 'video_count': r['video_count']} for r in (json.loads(row[0]) for row in rows)]

    def get(self, run_id: str):
        self.history()  # Enforce retention even if a user requests an old run directly.
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM runs WHERE id = ?', (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def previous(self, videos: list):
        previous = {}
        with self.connect() as conn:
            for v in videos:
                if v.synthetic:
                    continue
                oldest = (v.observed_at - timedelta(days=30)).isoformat()
                latest = (v.observed_at - timedelta(hours=1)).isoformat()
                row = conn.execute('''SELECT observed_at, views FROM observations
                    WHERE video_id = ? AND observed_at >= ? AND observed_at <= ?
                    AND views IS NOT NULL ORDER BY observed_at DESC LIMIT 1''',
                                   (v.id, oldest, latest)).fetchone()
                if row:
                    previous[v.id] = dict(row)
        return previous

    def clear(self):
        with self.connect() as conn:
            conn.execute('DELETE FROM observations')
            conn.execute('DELETE FROM runs')
