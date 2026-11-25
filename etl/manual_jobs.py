"""Local manual job journal. No Django migrations or source database writes."""
import io
import os
import re
import sqlite3
import subprocess
import sys
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ACTIVE = ('PENDING', 'RUNNING')
MODES = ('PREVIEW', 'APPLY')
SCHEMA = '''CREATE TABLE IF NOT EXISTS manual_job (
    job_id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('PREVIEW','APPLY')),
    actor_id INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN
        ('PENDING','RUNNING','SUCCESS','FAILED','INTERRUPTED')),
    created TEXT NOT NULL, started TEXT, finished TEXT, worker_pid INTEGER,
    run_id TEXT, stage TEXT, outcome TEXT, reason TEXT
)'''
INDEX = "CREATE UNIQUE INDEX IF NOT EXISTS one_active_manual_job ON manual_job ((1)) WHERE status IN ('PENDING','RUNNING')"
RUN = re.compile(r'\brun-id=(\d{8}T\d{6}Z_[0-9a-f]{8})(?=\s|$)')
STAGES = {'EXTRACT','MAPPING','QUALITY','TRANSFORM','LOAD','DIMENSIONS','FACTS'}
OUTCOMES = {'ETL_PREVIEW_ONLY','ETL_APPLIED','ETL_ALREADY_APPLIED'}

class BusyError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'manual_etl.sqlite3'

    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        db.row_factory = sqlite3.Row
        return db

    def reserve(self, mode, actor_id):
        if mode not in MODES or type(actor_id) is not int or actor_id <= 0:
            raise ValueError('Invalid manual job')
        self.root.mkdir(parents=True, exist_ok=True)
        # Advisory check only; run_etl's pipeline_lock is the final authority.
        if (self.root / '.pipeline.lock').exists():
            raise BusyError('Pipeline busy')
        job_id = uuid.uuid4().hex
        with closing(self.connect()) as db, db:
            db.execute(SCHEMA)
            db.execute(INDEX)
            try:
                db.execute('INSERT INTO manual_job(job_id, mode, actor_id, status, created) VALUES(?,?,?,?,?)',
                           (job_id, mode, actor_id, 'PENDING', now()))
            except sqlite3.IntegrityError as exc:
                raise BusyError('Manual job active') from exc
        return job_id

    def claim(self, job_id):
        with closing(self.connect()) as db, db:
            n = db.execute("UPDATE manual_job SET status='RUNNING', started=?, worker_pid=? WHERE job_id=? AND status='PENDING'",
                           (now(), os.getpid(), job_id)).rowcount
            if n != 1:
                return None
            return db.execute('SELECT mode FROM manual_job WHERE job_id=?', (job_id,)).fetchone()['mode']

    def progress(self, job_id, stage, run_id, outcome):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE manual_job SET stage=COALESCE(?,stage), run_id=COALESCE(?,run_id), outcome=COALESCE(?,outcome) WHERE job_id=? AND status='RUNNING'",
                       (stage, run_id, outcome, job_id))

    def finish(self, job_id, status, reason=None, *, expected='RUNNING'):
        if status not in ('SUCCESS','FAILED','INTERRUPTED') or expected not in ACTIVE:
            raise ValueError('Invalid transition')
        with closing(self.connect()) as db, db:
            return db.execute('UPDATE manual_job SET status=?, reason=?, finished=? WHERE job_id=? AND status=?',
                              (status, reason, now(), job_id, expected)).rowcount == 1

    def history(self, limit=20):
        if not self.path.exists():
            return []
        # No writes on monitoring GET, including no accidental database creation.
        with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
            db.row_factory = sqlite3.Row
            # Active entry always visible, even if the journal grows.
            return [dict(r) for r in db.execute("SELECT * FROM manual_job ORDER BY (status IN ('PENDING','RUNNING')) DESC, created DESC LIMIT ?", (limit,))]

    def interrupt(self, job_id):
        if (self.root / '.pipeline.lock').exists():
            raise BusyError('Pipeline lock exists; inspect before recovery')
        with closing(self.connect()) as db, db:
            return db.execute("UPDATE manual_job SET status='INTERRUPTED', reason='OPERATOR_CONFIRMED_STOPPED', finished=? WHERE job_id=? AND status IN ('PENDING','RUNNING')", (now(), job_id)).rowcount == 1


class ProgressOutput(io.TextIOBase):
    """Only persist allowlisted metadata; no raw command output or credentials."""
    def __init__(self, journal, job_id):
        self.journal, self.job_id = journal, job_id
        self.outcome = None

    def write(self, text):
        for line in text.splitlines():
            prefix = line.split(' | ', 1)[0]
            stage = prefix if prefix in STAGES else None
            outcome = prefix if prefix in OUTCOMES else None
            match = RUN.search(line) if stage == 'EXTRACT' or outcome else None
            if outcome:
                self.outcome = outcome
            if stage or outcome:
                try:
                    self.journal.progress(self.job_id, stage, match.group(1) if match else None, outcome)
                except (sqlite3.Error, OSError):
                    # Journal failure must not alter ETL transaction semantics.
                    pass
        return len(text)


def execute_job(journal, job_id, run):
    mode = journal.claim(job_id)
    if mode is None:
        return False
    output = ProgressOutput(journal, job_id)
    try:
        run(apply=mode == 'APPLY', stdout=output)
    except Exception:
        journal.finish(job_id, 'FAILED', 'CHECK_ETL_LOG_BEFORE_RETRY')
        return False
    expected = {'ETL_APPLIED','ETL_ALREADY_APPLIED'} if mode == 'APPLY' else {'ETL_PREVIEW_ONLY'}
    if output.outcome not in expected:
        journal.finish(job_id, 'FAILED', 'OUTCOME_UNCONFIRMED_CHECK_ETL_LOG')
        return False
    return journal.finish(job_id, 'SUCCESS')


def launch(journal, project_root, mode, actor_id):
    job_id = journal.reserve(mode, actor_id)
    argv = [sys.executable, str(Path(project_root) / 'manage.py'), 'run_manual_etl', '--job-id', job_id]
    kwargs = {'cwd': str(project_root), 'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
              'stderr': subprocess.DEVNULL, 'shell': False}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs['start_new_session'] = True
    try:
        process = subprocess.Popen(argv, **kwargs)
    except OSError:
        journal.finish(job_id, 'FAILED', 'WORKER_START_FAILED', expected='PENDING')
        raise
    # Reap child if web process stays alive; the ETL itself is in a separate process.
    try:
        threading.Thread(target=process.wait, daemon=True).start()
    except RuntimeError:
        pass
    return job_id
