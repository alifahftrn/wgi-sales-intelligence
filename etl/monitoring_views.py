"""Local admin ETL monitoring; reads operational summaries."""
import sqlite3
from datetime import datetime
from .manual_jobs import Journal, ACTIVE
from django.conf import settings
from django.db import connections, transaction, DatabaseError
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache
from .monitoring import read_database, scheduler_attempts


@never_cache
@require_safe
def etl_monitor(request):
    if not settings.DEBUG or request.META.get('REMOTE_ADDR') not in {'127.0.0.1','::1'}:
        return HttpResponseForbidden('Monitoring development hanya untuk localhost.')
    history, latest_fact, attempts = [], None, []
    database_error = scheduler_error = False
    try:
        with transaction.atomic(using='datamart'):
            with connections['datamart'].cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                history, latest_fact = read_database(cursor)
    except DatabaseError:
        database_error = True
    try:
        attempts = scheduler_attempts(settings.EXTRACT_ROOT.parent / 'scheduler_logs')
    except OSError:
        scheduler_error = True
    manual_error = False
    manual_jobs = []
    pipeline_busy = True
    try:
        root = settings.EXTRACT_ROOT.parent
        manual_jobs = Journal(root).history()
        pipeline_busy = (root / '.pipeline.lock').exists() or any(j['status'] in ACTIVE for j in manual_jobs)
        for job in manual_jobs:
            for key in ('created', 'started', 'finished'):
                if job[key]:
                    job[key] = datetime.fromisoformat(job[key])
    except (OSError, sqlite3.Error, ValueError):
        manual_error = True
        pipeline_busy = True
    return render(request, 'etl_monitor_v1.html', dict(history=history, latest_fact=latest_fact,
                  attempts=attempts, latest=attempts[0] if attempts else None,
                  database_error=database_error, scheduler_error=scheduler_error,
                  manual_jobs=manual_jobs, manual_error=manual_error, pipeline_busy=pipeline_busy))
