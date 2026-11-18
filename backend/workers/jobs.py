"""Background decoder jobs; progress counts completed real process executions."""
from __future__ import annotations
import os
import signal
import threading
from pathlib import Path
from backend.storage.database import Database
from backend.workers.runner import execute


class JobManager:
    def __init__(self, db: Database):
        self.db = db
        self.lock = threading.Lock()
        self.active: dict[str, dict] = {}
        with db.connect() as c:
            c.execute("UPDATE jobs SET status='interrupted', error='Backend stopped before the job finished.' WHERE status IN ('queued','running')")

    def start(self, session_id: str, files: list[dict], decoders: list[str], timeout: float, memory_mb: int, repeats: int) -> dict:
        config = {'file_ids':[f['id'] for f in files], 'decoders':decoders, 'timeout_seconds':timeout, 'memory_mb':memory_mb, 'repeats':repeats}
        event = threading.Event()
        with self.lock:
            if self.active: raise RuntimeError('Another decoder job is already running')
            job = self.db.create_job(session_id,len(files)*len(decoders)*repeats,config)
            self.active[job['id']] = {'event':event, 'pid':None}
        thread = threading.Thread(target=self._work,args=(job['id'],session_id,files,decoders,timeout,memory_mb,repeats,event),daemon=True)
        thread.start()
        return job

    def _work(self, job_id, session_id, files, decoders, timeout, memory_mb, repeats, event):
        completed = 0
        self.db.update_job(job_id,status='running')
        def pid_changed(pid):
            with self.lock:
                if job_id in self.active: self.active[job_id]['pid'] = pid
                if pid and event.is_set():
                    try: os.killpg(pid,signal.SIGKILL)
                    except ProcessLookupError: pass
        try:
            for file in files:
                for decoder in decoders:
                    for repeat in range(repeats):
                        if event.is_set(): break
                        result = execute(Path(file['path']),decoder,timeout,memory_mb,event,pid_changed)
                        result['repeat'] = repeat + 1
                        self.db.add_run(job_id,session_id,file['id'],decoder,result)
                        completed += 1
                        self.db.update_job(job_id,completed=completed)
                    if event.is_set(): break
                if event.is_set(): break
            self.db.update_job(job_id,status='canceled' if event.is_set() else 'completed')
        except Exception as exc:
            self.db.update_job(job_id,status='failed',error=f'{type(exc).__name__}: {exc}')
        finally:
            with self.lock: self.active.pop(job_id,None)

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            job = self.active.get(job_id)
            if not job: return False
            job['event'].set()
            if job['pid']:
                try: os.killpg(job['pid'],signal.SIGKILL)
                except ProcessLookupError: pass
            return True

    def current_pid(self, job_id: str) -> int | None:
        with self.lock: return self.active.get(job_id,{}).get('pid')

    def has_active(self) -> bool:
        with self.lock: return bool(self.active)
