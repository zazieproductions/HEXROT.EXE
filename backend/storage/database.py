"""SQLite index and UUID-addressed private workspace; callers never supply paths."""
from __future__ import annotations
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any
from backend.config import HOME
from backend.parsers.audio import analyze


def now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def clean_name(name: str) -> str:
    name = Path(name.replace('\\', '/')).name
    return ''.join(c for c in name if c.isprintable() and c not in '/\\')[:160] or 'upload.bin'


class Database:
    def __init__(self, root: Path | None = None):
        self.root = (root or HOME).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = self.root / 'research.sqlite3'
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, analysis TEXT NOT NULL, mutation TEXT);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, status TEXT NOT NULL, total INTEGER NOT NULL, completed INTEGER NOT NULL, created_at TEXT NOT NULL, config TEXT NOT NULL, error TEXT);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, session_id TEXT NOT NULL, file_id TEXT NOT NULL, decoder TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS triage (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, run_id TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL);
            ''')

    def connect(self):
        connection = sqlite3.connect(self.db, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def create_session(self, name: str) -> dict:
        item = {'id': uuid.uuid4().hex, 'name':clean_name(name), 'created_at':now()}
        with self.connect() as c:
            c.execute('INSERT INTO sessions VALUES (:id,:name,:created_at)', item)
        (self.root / item['id']).mkdir(mode=0o700)
        return item

    def list_sessions(self) -> list[dict]:
        with self.connect() as c:
            rows = c.execute('SELECT s.*, (SELECT count(*) FROM files f WHERE f.session_id=s.id) AS file_count FROM sessions s ORDER BY created_at DESC LIMIT 100').fetchall()
        return [dict(x) for x in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self.connect() as c:
            row = c.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        return dict(row) if row else None

    def add_file(self, session_id: str, name: str, data: bytes, kind: str, mutation: dict | None = None) -> dict:
        if not self.get_session(session_id): raise KeyError('Session not found')
        file_id = uuid.uuid4().hex
        name = clean_name(name)
        path = self.root / session_id / file_id
        with path.open('xb') as f:
            os.chmod(path, 0o600)
            f.write(data)
        try:
            analysis = analyze(path, name)
            item = {'id':file_id, 'session_id':session_id, 'name':name, 'path':str(path), 'kind':kind,
                    'created_at':now(), 'analysis':json.dumps(analysis), 'mutation':json.dumps(mutation) if mutation else None}
            with self.connect() as c:
                c.execute('INSERT INTO files VALUES (:id,:session_id,:name,:path,:kind,:created_at,:analysis,:mutation)', item)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.get_file(session_id, file_id)  # type: ignore

    def get_file(self, session_id: str, file_id: str, internal: bool = False) -> dict | None:
        with self.connect() as c:
            row = c.execute('SELECT * FROM files WHERE session_id=? AND id=?', (session_id,file_id)).fetchone()
        return self._file(row, internal) if row else None

    def list_files(self, session_id: str, internal: bool = False) -> list[dict]:
        with self.connect() as c:
            rows = c.execute('SELECT * FROM files WHERE session_id=? ORDER BY created_at,id', (session_id,)).fetchall()
        return [self._file(row, internal) for row in rows]

    @staticmethod
    def _file(row: sqlite3.Row, internal: bool = False) -> dict:
        result = dict(row)
        result['analysis'] = json.loads(result['analysis'])
        result['mutation'] = json.loads(result['mutation']) if result['mutation'] else None
        if not internal: result.pop('path')
        return result

    def create_job(self, session_id: str, total: int, config: dict) -> dict:
        item = {'id':uuid.uuid4().hex, 'session_id':session_id, 'status':'queued', 'total':total, 'completed':0, 'created_at':now(), 'config':json.dumps(config), 'error':None}
        with self.connect() as c:
            c.execute('INSERT INTO jobs VALUES (:id,:session_id,:status,:total,:completed,:created_at,:config,:error)', item)
        return self.get_job(item['id'])  # type: ignore

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as c:
            row = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row: return None
        result = dict(row); result['config'] = json.loads(result['config'])
        return result

    def list_jobs(self, session_id: str) -> list[dict]:
        with self.connect() as c:
            ids = [row['id'] for row in c.execute('SELECT id FROM jobs WHERE session_id=? ORDER BY created_at DESC', (session_id,))]
        return [self.get_job(i) for i in ids]  # type: ignore

    def update_job(self, job_id: str, *, status: str | None = None, completed: int | None = None, error: str | None = None) -> None:
        with self.connect() as c:
            if status is not None: c.execute('UPDATE jobs SET status=? WHERE id=?', (status,job_id))
            if completed is not None: c.execute('UPDATE jobs SET completed=? WHERE id=?', (completed,job_id))
            if error is not None: c.execute('UPDATE jobs SET error=? WHERE id=?', (error[:500],job_id))

    def add_run(self, job_id: str, session_id: str, file_id: str, decoder: str, result: dict) -> dict:
        item = {'id':uuid.uuid4().hex,'job_id':job_id,'session_id':session_id,'file_id':file_id,'decoder':decoder,'created_at':now(),'result':json.dumps(result)}
        with self.connect() as c:
            c.execute('INSERT INTO runs VALUES (:id,:job_id,:session_id,:file_id,:decoder,:created_at,:result)', item)
        item['result'] = result
        return item

    def list_runs(self, session_id: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute('SELECT * FROM runs WHERE session_id=? ORDER BY created_at,id', (session_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row); item['result'] = json.loads(item['result']); result.append(item)
        return result

    def add_triage(self, session_id: str, run_id: str, result: dict) -> dict:
        item = {'id':uuid.uuid4().hex,'session_id':session_id,'run_id':run_id,'created_at':now(),'result':json.dumps(result)}
        with self.connect() as c:
            c.execute('INSERT INTO triage VALUES (:id,:session_id,:run_id,:created_at,:result)',item)
        item['result'] = result
        return item

    def list_triage(self, session_id: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute('SELECT * FROM triage WHERE session_id=? ORDER BY created_at', (session_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row); item['result'] = json.loads(item['result']); items.append(item)
        return items
