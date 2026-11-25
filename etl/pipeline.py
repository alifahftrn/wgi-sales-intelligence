"""MySQL full-snapshot orchestration. Database caller owns one atomic transaction."""
from contextlib import contextmanager
from pathlib import Path
import yaml
from etl.mapping.engine import RUN_ID
from etl.mapping.full_engine import map_full_run
from etl.load.dimensions import prepare, execute as load_dimensions
from etl.load.fact_writer import execute as load_facts
from etl.transform.plan_engine import CONFIG, preview


@contextmanager
def pipeline_lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.pipeline.lock'
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError('Pipeline sedang berjalan atau lock tertinggal; periksa proses sebelum membersihkan lock') from exc
    try:
        yield
    finally:
        lock.rmdir()


def prepare_run(raw_root, run_id=None, *, extract, progress=lambda *_: None):
    """New extraction or explicit resume. Never overwrite mapping output."""
    raw_root = Path(raw_root)
    canonical = raw_root.parent / 'canonical_v2'
    if run_id is None:
        progress('EXTRACT', 'START')
        result = extract(source='mysql')
        run_id = result['run_id']
        progress('EXTRACT', f'OK | run-id={run_id} | rows={result["total_rows"]}')
    else:
        progress('EXTRACT', 'REUSE | run-id=' + run_id)
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('run-id tidak valid')
    progress('MAPPING', 'START')
    if (canonical / 'mysql' / run_id).exists():
        progress('MAPPING', 'REUSE | checksum akan diperiksa')
    else:
        mapped = map_full_run(raw_root, canonical, run_id)
        if mapped['status'] != 'SUCCESS' or mapped['quarantine']:
            raise ValueError('Mapping memiliki quarantine; pipeline dihentikan')
        progress('MAPPING', f'OK | ready={mapped["ready"]}')
    progress('QUALITY', 'START')
    p = prepare(raw_root, canonical, run_id)
    progress('QUALITY', f'OK | warnings={p["warnings"]} | status policy diperiksa Transform')
    progress('TRANSFORM', 'START')
    v = preview(p['data'], p['cutoff'], p['cutoff'], yaml.safe_load(CONFIG.read_text(encoding='utf-8')))
    summary = v['summary']
    progress('TRANSFORM', f'OK | actual_pack={summary["actual_pack"]} | monthly_rows={summary["monthly_metric_rows"]}')
    return p, summary


def load_atomic(cursor, prepared, *, apply=False, test_only=False):
    """Caller must wrap BOTH loaders in one database transaction; never commit here.

    In preview, new dimension versions are not persisted. The fact database check
    requires a matching dimension log; defer it for a new run until apply.
    """
    d = load_dimensions(cursor, prepared, apply, test_only=test_only)
    expected = {'DIMENSIONS_APPLIED', 'ALREADY_APPLIED'} if apply else {'DRY_RUN', 'ALREADY_APPLIED'}
    if d['status'] not in expected:
        raise ValueError('status dimension loader tidak valid')
    if not apply and d['status'] == 'DRY_RUN':
        return {'status':'ETL_PREVIEW_ONLY', 'dimensions':d, 'facts':None, 'fact_db_check':'DEFERRED_UNTIL_APPLY'}
    f = load_facts(cursor, prepared, apply, test_only=test_only)
    expected = {'FACTS_APPLIED', 'ALREADY_APPLIED'} if apply else {'DRY_RUN', 'ALREADY_APPLIED'}
    if f['status'] not in expected:
        raise ValueError('status fact loader tidak valid')
    status = 'ETL_PREVIEW_ONLY' if not apply else ('ETL_ALREADY_APPLIED' if d['status']==f['status']=='ALREADY_APPLIED' else 'ETL_APPLIED')
    return {'status':status, 'dimensions':d, 'facts':f, 'fact_db_check':'COMPLETE'}
