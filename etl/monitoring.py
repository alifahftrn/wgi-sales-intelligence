"""Read-only operational summaries. Never expose raw stdout/stderr or errors."""
from datetime import datetime
from pathlib import Path
import re

STAMP = re.compile(r'\d{8}T\d{9}Z_[0-9a-f]{8}')
RUN = re.compile(r'\d{8}T\d{6}Z_[0-9a-f]{8}')
START = re.compile(r'START \| mode=(PREVIEW|APPLY) \| utc=(\S+)')
END = re.compile(r'(SUCCESS|FAILED) \| exit_code=(-?\d+) \| utc=(\S+)(?: \| .*)?')
OUTCOME = re.compile(r'^(ETL_PREVIEW_ONLY|ETL_APPLIED|ETL_ALREADY_APPLIED) \| run-id=(\d{8}T\d{6}Z_[0-9a-f]{8})(?: \|.*)?$')
STAGES = ('EXTRACT', 'MAPPING', 'QUALITY', 'TRANSFORM', 'DIMENSIONS', 'FACTS')
STAGE_STATES = {'START','OK','REUSE','DRY_RUN','ALREADY_APPLIED','DIMENSIONS_APPLIED','FACTS_APPLIED','DEFERRED_UNTIL_APPLY'}


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def read_small(path, maximum=65536):
    try:
        if path.is_symlink():
            return None
        with path.open('rb') as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            return None
        return raw.decode('utf-8-sig')
    except (OSError, UnicodeError):
        return None


def summarize_attempt(path):
    name = path.name.removesuffix('.status.txt')
    item = dict(attempt=name, mode='UNKNOWN', status='UNKNOWN', started=None,
                finished=None, exit_code=None, run_id=None, outcome=None,
                stages=[], stderr_present=None)
    content = read_small(path, 16384)
    if content is None:
        return item
    lines = content.splitlines()
    start = START.fullmatch(lines[0]) if lines else None
    if start:
        item['mode'], item['started'] = start.group(1), parse_time(start.group(2))
        item['status'] = 'NO_FINAL_STATUS'
    finish = END.fullmatch(lines[-1]) if len(lines) > 1 else None
    if start and finish:
        item['finished'] = parse_time(finish.group(3))
        item['exit_code'] = int(finish.group(2))
        if item['started'] and item['finished'] and item['finished'] >= item['started']:
            if finish.group(1) == 'SUCCESS' and item['exit_code'] == 0:
                item['status'] = 'SUCCESS'
            elif finish.group(1) == 'FAILED' and item['exit_code'] != 0:
                item['status'] = 'FAILED'
            else:
                item['status'] = 'UNKNOWN'
    output = read_small(path.with_name(name + '.stdout.log'))
    states = {}
    if output is not None:
        for line in output.splitlines():
            parts = line.split(' | ', 2)
            if len(parts) >= 2 and parts[0] in STAGES and parts[1] in STAGE_STATES:
                states[parts[0]] = parts[1]
            match = OUTCOME.fullmatch(line)
            if match:
                item['outcome'], item['run_id'] = match.groups()
        item['stages'] = [(stage, states.get(stage, 'NOT_REPORTED')) for stage in STAGES]
    err = path.with_name(name + '.stderr.log')
    try:
        if not err.is_symlink() and err.is_file():
            item['stderr_present'] = err.stat().st_size > 0
    except OSError:
        pass
    return item


def scheduler_attempts(root, limit=20):
    root = Path(root)
    if not root.exists():
        return []
    paths = [p for p in root.glob('*.status.txt')
             if STAMP.fullmatch(p.name.removesuffix('.status.txt')) and not p.is_symlink()]
    return [summarize_attempt(p) for p in sorted(paths, key=lambda p:p.name, reverse=True)[:limit]]


SQL = '''SELECT id_run, run_key, mulai_at, selesai_at, cutoff_at, status,
                 rows_read, rows_written, rows_quarantine
          FROM public.etl_log WHERE source_system = %s
          ORDER BY id_run DESC LIMIT %s'''
LATEST_FACT_SQL = '''SELECT id_run, run_key, mulai_at, selesai_at, cutoff_at, status,
                 rows_read, rows_written, rows_quarantine
          FROM public.etl_log WHERE source_system = %s AND status = 'SUCCESS'
          AND run_key LIKE %s ORDER BY cutoff_at DESC, id_run DESC LIMIT 1'''


def summarize_db_row(row):
    ident, key, start, finish, cutoff, status, read, written, quarantine = row
    prefix, _, run_id = key.partition(':')
    stage = {'DIM_V1':'DIMENSIONS','FACT_V1':'FACTS'}.get(prefix, 'OTHER')
    return dict(id=ident, stage=stage, run_id=run_id if RUN.fullmatch(run_id) else 'UNKNOWN',
                started=start, finished=finish, cutoff=cutoff, status=status,
                rows_read=read, rows_written=written, quarantine=quarantine,
                duration=round((finish-start).total_seconds(), 3) if finish and start else None)


def read_database(cursor):
    cursor.execute(SQL, ('MYSQL', 50))
    history = [summarize_db_row(row) for row in cursor.fetchall()]
    cursor.execute(LATEST_FACT_SQL, ('MYSQL', 'FACT_V1:%'))
    row = cursor.fetchone()
    return history, summarize_db_row(row) if row else None
