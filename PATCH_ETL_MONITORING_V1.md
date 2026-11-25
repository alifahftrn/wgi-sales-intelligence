# ETL Monitoring V1 — read-only, development

Extract all six files into project root. No replacement files. Register a new route manually in `config/urls.py`, after the existing urlpatterns:

```python
from etl.monitoring_views import etl_monitor
urlpatterns += [path('etl/monitoring/', etl_monitor, name='etl_monitor_v1')]
```

The original config already imports `path`; keep existing routes. Do not duplicate this addition. Start `python manage.py runserver 127.0.0.1:8000` and open `/etl/monitoring/`. Run `python -m unittest discover -v` and `python manage.py check` first.

The new view uses read-only PostgreSQL transactions against `datamart`, selects 50 latest MYSQL log rows and latest successful fact cutoff, and reads up to 20 scheduler status files with bounded contents and strict filenames. It displays status fields only, not raw errors or logs. Preview and Apply attempts are separate from committed load logs. Incomplete status does not prove the process is running. Existing loader labels `trigger=MANUAL` even for scheduled jobs, so no trigger inference is made from that field. Dates in Asia/Jakarta. No automatic polling or write action. No new dependency or migrations. No use of `migrate`.

Local development only: DEBUG=True and loopback remote address required. No login configured; do not expose via proxy/network. Manual trigger and production deployment require authenticated role checks, persistent job state and a dedicated worker. Current scheduler history only captures PowerShell attempts, not direct CLI failures or OS runs that fail before script starts. Source coverage remains unverified. No OS schedule query. The old Extract-only page remains unchanged.

Git add the six patch files and config/urls.py after testing. Do not commit `.local` logs or `.env`.
