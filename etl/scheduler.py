"""Single-host daily WIB scheduler. No business database schema changes."""
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .manual_jobs import ProgressOutput, Journal, ACTIVE, MODES

WIB = timezone(timedelta(hours=7), 'WIB')
GRACE = timedelta(minutes=5)
DEFAULT = dict(enabled=0, clock='00:00', mode='PREVIEW', updated=None)
CONFIG = '''CREATE TABLE IF NOT EXISTS schedule_config (
 id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 clock TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN ('PREVIEW','APPLY')), updated TEXT NOT NULL)'''
JOBS = '''CREATE TABLE IF NOT EXISTS schedule_run (
 job_id TEXT PRIMARY KEY, clock TEXT NOT NULL, mode TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED','INTERRUPTED')),
 started TEXT NOT NULL, finished TEXT, stage TEXT, run_id TEXT, outcome TEXT, reason TEXT)'''
ACTIVE_INDEX = "CREATE UNIQUE INDEX IF NOT EXISTS one_running_schedule ON schedule_run ((1)) WHERE status='RUNNING'"


def utc_now():
    return datetime.now(timezone.utc)


def stamp():
    return utc_now().isoformat()


def due_slot(config, instant):
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Timezone-aware datetime required')
    if not config['enabled']:
        return None
    local = instant.astimezone(WIB)
    h, m = map(int, config['clock'].split(':'))
    due = local.replace(hour=h, minute=m, second=0, microsecond=0)
    # Also handles a 23:59 window that extends past midnight.
    if local < due:
        due -= timedelta(days=1)
    return due.date().isoformat() if timedelta(0) <= local - due < GRACE else None


class Scheduler:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'scheduler_v2.sqlite3'

    def connect(self, readonly=False):
        target = self.path.resolve().as_uri() + '?mode=ro' if readonly else self.path
        db = sqlite3.connect(target, uri=readonly, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def initialize(db):
        db.execute(CONFIG)
        db.execute(JOBS)
        db.execute(ACTIVE_INDEX)

    @staticmethod
    def config(db):
        row = db.execute('SELECT enabled,clock,mode,updated FROM schedule_config WHERE id=1').fetchone()
        return dict(row) if row else DEFAULT.copy()

    def configure(self, *, enabled, clock, mode, confirm_apply=False):
        if type(enabled) is not bool or mode not in MODES or not isinstance(clock, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', clock):
            raise ValueError('Jadwal harus HH:MM WIB, mode PREVIEW/APPLY')
        if enabled and mode == 'APPLY' and not confirm_apply:
            raise ValueError('Konfirmasi APPLY diperlukan')
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self.initialize(db)
            db.execute('INSERT INTO schedule_config VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,clock=excluded.clock,mode=excluded.mode,updated=excluded.updated', (int(enabled), clock, mode, stamp()))

    def status(self):
        if not self.path.exists():
            return DEFAULT.copy(), []
        with closing(self.connect(readonly=True)) as db:
            db.execute('BEGIN')
            return self.config(db), [dict(r) for r in db.execute("SELECT * FROM schedule_run ORDER BY (status='RUNNING') DESC, job_id DESC LIMIT 20")]

    def claim(self, instant):
        if not self.path.exists():
            return 'DISABLED', None
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            config = self.config(db)
            if not config['enabled']:
                return 'DISABLED', None
            if db.execute("SELECT 1 FROM schedule_run WHERE status='RUNNING'").fetchone():
                return 'ACTIVE_OR_INTERRUPTED', None
            slot = due_slot(config, instant)
            if slot is None:
                return 'NOT_DUE', None
            if db.execute('SELECT 1 FROM schedule_run WHERE job_id=?', (slot,)).fetchone():
                return 'ALREADY_ATTEMPTED', None
            # Advisory only: run_etl acquires the authoritative shared lock.
            if (self.root / '.pipeline.lock').exists() or any(j['status'] in ACTIVE for j in Journal(self.root).history()):
                return 'BUSY', None
            db.execute('INSERT INTO schedule_run(job_id,clock,mode,status,started) VALUES(?,?,?,?,?)', (slot, config['clock'], config['mode'], 'RUNNING', instant.astimezone(timezone.utc).isoformat()))
            return 'CLAIMED', (slot, config['mode'])

    def progress(self, job_id, stage, run_id, outcome):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE schedule_run SET stage=COALESCE(?,stage),run_id=COALESCE(?,run_id),outcome=COALESCE(?,outcome) WHERE job_id=? AND status='RUNNING'", (stage,run_id,outcome,job_id))

    def finish(self, job_id, status, reason=None):
        if status not in ('SUCCESS','FAILED','INTERRUPTED'):
            raise ValueError('Invalid final status')
        with closing(self.connect()) as db, db:
            return db.execute("UPDATE schedule_run SET status=?,reason=?,finished=? WHERE job_id=? AND status='RUNNING'",(status,reason,stamp(),job_id)).rowcount == 1

    def recover(self, job_id, *, confirmed=False):
        if not confirmed or (self.root / '.pipeline.lock').exists():
            raise ValueError('Pastikan worker berhenti dan shared lock tidak aktif sebelum recovery')
        if not self.path.exists():
            return False
        return self.finish(job_id,'INTERRUPTED','OPERATOR_CONFIRMED_STOPPED')

    def tick(self, run, instant=None):
        state, claimed = self.claim(instant if instant is not None else utc_now())
        if claimed is None:
            return state
        slot, mode = claimed
        output = ProgressOutput(self, slot)
        try:
            run(apply=mode == 'APPLY', stdout=output)
        except Exception:
            self.finish(slot, 'FAILED','CHECK_ETL_LOG_BEFORE_RETRY')
            return 'FAILED'
        expected = {'ETL_APPLIED','ETL_ALREADY_APPLIED'} if mode == 'APPLY' else {'ETL_PREVIEW_ONLY'}
        if output.outcome not in expected:
            self.finish(slot,'FAILED','OUTCOME_UNCONFIRMED_CHECK_ETL_LOG')
            return 'FAILED'
        if not self.finish(slot,'SUCCESS'):
            return 'STATUS_UNCONFIRMED'
        return 'SUCCESS'
